import { test, expect, Page } from '@playwright/test'

/**
 * Manual event certificates on devlms.
 *
 * Live events hand out certificates by hand (after an external quiz), so an
 * event in `credit_verification = Manual` never mints on its own. The admin
 * selects attendees on the Dashboard and clicks "Issue certificate".
 *
 * Dev setup these tests assume (same as event-credit-verification.spec.ts):
 *   - moderator-smoke@test.com / TestUser@2026! has the Moderator role
 *   - global-admin@test.com / TestUser@2026! is a Global Admin
 *   - pro@test.com / TestUser@2026! is a plain learner
 *   - The shared "Course Survey" quiz (is_survey=1) exists
 */

const PASSWORD = 'TestUser@2026!'
const SEED_EMAIL = 'moderator-smoke@test.com'
const ADMIN_EMAIL = 'global-admin@test.com'
const STUDENT_EMAIL = 'pro@test.com'
const STAMP = Date.now().toString(36)
const TITLE = `E2E Manual Cert ${STAMP}`

test.describe.configure({ mode: 'serial' })
test.setTimeout(120000)

const ctx: { event?: string } = {}
const leftovers: string[] = []

async function login(page: Page, email: string) {
	await page.goto('/login')
	await page.fill('#login_email', email)
	await page.fill('#login_password', PASSWORD)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function logout(page: Page) {
	await page.goto('/api/method/logout')
	await page.waitForLoadState('networkidle').catch(() => {})
}

async function api(page: Page, method: string, data: Record<string, unknown>) {
	const csrf = await page.evaluate(() => (window as any).csrf_token as string)
	const res = await page.request.post(`/api/method/${method}`, {
		headers: { 'X-Frappe-CSRF-Token': csrf },
		data,
	})
	const text = await res.text()
	if (!res.ok()) throw new Error(`${method} failed: ${text}`)
	return JSON.parse(text).message
}

async function insert(page: Page, doc: Record<string, unknown>) {
	return api(page, 'frappe.client.insert', { doc: JSON.stringify(doc) })
}

async function listNames(page: Page, doctype: string, filters: Record<string, unknown>) {
	const rows = await api(page, 'frappe.client.get_list', {
		doctype,
		filters: JSON.stringify(filters),
		fields: JSON.stringify(['name']),
		limit_page_length: 100,
	})
	return (rows || []).map((r: { name: string }) => r.name)
}

async function tryDelete(page: Page, doctype: string, name: string) {
	await api(page, 'frappe.client.delete', { doctype, name }).catch(() => {
		leftovers.push(`${doctype}: ${name}`)
	})
}

function yesterday() {
	const d = new Date()
	d.setDate(d.getDate() - 1)
	return d.toISOString().slice(0, 10)
}

test.describe('Manual event certificates', () => {
	test.beforeAll(async ({ browser }) => {
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)

		const surveys = await listNames(page, 'LMS Quiz', { is_survey: 1, title: 'Course Survey' })
		if (!surveys.length) throw new Error('Shared "Course Survey" quiz not found on dev')

		const day = yesterday()
		// No credit_verification on purpose: Manual must be the default.
		const doc = await insert(page, {
			doctype: 'LMS Event',
			title: TITLE,
			start_date: day,
			end_date: day,
			start_time: '09:00:00',
			end_time: '10:00:00',
			event_days: [{ date: day, start_time: '09:00:00', end_time: '10:00:00' }],
			timezone: 'America/New_York',
			description: 'E2E manual certificate event',
			event_details: '<p>E2E manual certificate event</p>',
			instructors: [{ instructor: SEED_EMAIL }],
			certification: 1,
			credit_hours: 1,
			survey_quiz: surveys[0],
			published: 1,
		})
		expect(doc.credit_verification).toBe('Manual')
		ctx.event = doc.name
		await insert(page, {
			doctype: 'LMS Event Registration',
			event: doc.name,
			member: STUDENT_EMAIL,
		})
		await page.close()
	})

	test.afterAll(async ({ browser }) => {
		if (!ctx.event) return
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)
		for (const doctype of ['LMS Certificate', 'LMS Quiz Submission']) {
			for (const name of await listNames(page, doctype, { event_name: ctx.event })) {
				await tryDelete(page, doctype, name)
			}
		}
		for (const name of await listNames(page, 'LMS Event Registration', { event: ctx.event })) {
			await tryDelete(page, 'LMS Event Registration', name)
		}
		await tryDelete(page, 'LMS Event', ctx.event)
		await page.close()
		if (leftovers.length) {
			console.warn(
				`event-manual-certificates: ${leftovers.length} fixture(s) could not be deleted. Sweep on dev:\n  ` +
					leftovers.join('\n  ')
			)
		}
	})

	test('nothing issues on its own; the admin issues to selected attendees', async ({
		page,
		browser,
	}) => {
		// Student: certificate pending, and the survey banner no longer
		// promises a certificate.
		await login(page, STUDENT_EMAIL)
		await page.goto(`/lms/events/${ctx.event}#dashboard`)
		const progress = page.getByTestId('credit-progress')
		await expect(progress).toBeVisible({ timeout: 15000 })
		await expect(progress.getByText('Pending').last()).toBeVisible()
		await expect(page.getByText('Let us know how the event went.')).toBeVisible()
		await expect(page.getByText('Submit your feedback to receive your certificate.')).toHaveCount(0)

		// Admin: select the attendee and issue.
		const adminContext = await browser.newContext()
		const admin = await adminContext.newPage()
		await login(admin, ADMIN_EMAIL)
		await admin.goto(`/lms/events/${ctx.event}#dashboard`)
		await expect(admin.getByText('Students')).toBeVisible({ timeout: 15000 })

		// Only one attendee is registered, so the header "select all" is
		// equivalent to picking their row.
		await admin.locator('input[type="checkbox"]').first().check()
		await admin.getByRole('button', { name: 'Issue certificate' }).first().click()

		const dialog = admin.getByRole('dialog')
		await expect(dialog).toContainText('No survey or quiz result is checked')
		await dialog.getByRole('button', { name: 'Issue certificate' }).click()

		await expect(
			admin.getByText(/Certificate issued to/i).filter({ visible: true }).first()
		).toBeVisible({ timeout: 15000 })
		await expect(admin.getByText('Issued').first()).toBeVisible()

		// Student sees it, exactly one certificate exists, and it is published.
		await page.reload()
		await expect(progress).toContainText('Issued', { timeout: 15000 })
		const certs = await api(page, 'frappe.client.get_list', {
			doctype: 'LMS Certificate',
			filters: JSON.stringify({ event_name: ctx.event, member: STUDENT_EMAIL }),
			fields: JSON.stringify(['name', 'published']),
		})
		expect(certs.length).toBe(1)
		expect(certs[0].published).toBe(1)

		// Issuing again skips rather than duplicating.
		await admin.reload()
		await admin.locator('input[type="checkbox"]').first().check()
		await admin.getByRole('button', { name: 'Issue certificate' }).first().click()
		await admin.getByRole('dialog').getByRole('button', { name: 'Issue certificate' }).click()
		await expect(
			admin.getByText(/already certified, skipped/i).filter({ visible: true }).first()
		).toBeVisible({ timeout: 15000 })
		const again = await listNames(page, 'LMS Certificate', { event_name: ctx.event })
		expect(again.length).toBe(1)

		await adminContext.close()
		await logout(page)
	})
})
