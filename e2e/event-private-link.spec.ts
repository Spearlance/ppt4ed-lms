import { test, expect, Page } from '@playwright/test'

/**
 * Private registration link on devlms: an unpublished event hands out one
 * unlisted link, and whoever opens it can log in and register for free.
 *
 * Dev setup this assumes:
 *   - moderator-smoke@test.com / TestUser@2026! (Moderator) seeds the event
 *   - global-admin@test.com / TestUser@2026! (Global Admin) uses the Dashboard
 *   - pro@test.com / TestUser@2026! is a learner with a complete license
 *
 * The event is created at the start and deleted at the end.
 */

const PASSWORD = 'TestUser@2026!'
const SEED_EMAIL = 'moderator-smoke@test.com'
const ADMIN_EMAIL = 'global-admin@test.com'
const STUDENT_EMAIL = 'pro@test.com'
const TITLE = `E2E Private Link ${Date.now().toString(36)}`

test.describe.configure({ mode: 'serial' })
test.setTimeout(120000)

let eventName = ''
let linkUrl = ''

async function login(page: Page, email: string) {
	await page.goto('/login')
	await page.fill('#login_email', email)
	await page.fill('#login_password', PASSWORD)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
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

test.beforeAll(async ({ browser }) => {
	const page = await browser.newPage()
	await login(page, SEED_EMAIL)
	const day = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10)
	const doc = await api(page, 'frappe.client.insert', {
		doc: JSON.stringify({
			doctype: 'LMS Event',
			title: TITLE,
			published: 0,
			allow_self_enrollment: 0,
			start_date: day,
			end_date: day,
			start_time: '09:00:00',
			end_time: '11:00:00',
			timezone: 'America/New_York',
			description: 'Private link e2e event.',
			event_details: 'Private link e2e event.',
			instructors: [{ instructor: SEED_EMAIL }],
		}),
	})
	eventName = doc.name
	await page.close()
})

test.afterAll(async ({ browser }) => {
	if (!eventName) return
	const page = await browser.newPage()
	await login(page, SEED_EMAIL)
	const rows = await api(page, 'frappe.client.get_list', {
		doctype: 'LMS Event Registration',
		filters: JSON.stringify({ event: eventName }),
		fields: JSON.stringify(['name']),
	})
	const regs = rows.map((row: { name: string }) => row.name)
	if (regs.length) {
		await api(page, 'lms.lms.ceu_event_admin.remove_event_registrations', {
			event: eventName,
			registrations: JSON.stringify(regs),
		})
	}
	await api(page, 'lms.lms.api.delete_event', { event: eventName }).catch((e) =>
		console.warn(`Could not delete ${eventName}: ${e}`)
	)
	await page.close()
})

test('admin creates the private link from the Dashboard', async ({ page }) => {
	await login(page, ADMIN_EMAIL)
	await page.goto(`/lms/events/${eventName}#dashboard`)
	await page.getByRole('button', { name: 'Private link' }).click()
	const dialog = page.getByRole('dialog')
	await dialog.getByRole('button', { name: 'Create private link' }).click()
	const input = dialog.locator('input[readonly]')
	await expect(input).toHaveValue(new RegExp(`/lms/events/${eventName}/join/[0-9a-f]{24}$`))
	linkUrl = await input.inputValue()
})

test('guest sees the event through the link, and nothing with a bad code', async ({ browser }) => {
	const context = await browser.newContext()
	const page = await context.newPage()
	await page.goto(linkUrl)
	await expect(page.getByRole('heading', { name: TITLE })).toBeVisible()
	await expect(
		page.getByRole('button', { name: 'Create an account or log in to register' })
	).toBeVisible()
	await page.getByRole('button', { name: 'Create an account or log in to register' }).click()
	await expect(page.getByTestId('register-license-fields')).toBeVisible()

	await page.goto(linkUrl.slice(0, -4) + 'zzzz')
	await expect(page.getByTestId('private-join-invalid')).toBeVisible()
	await expect(page.getByRole('heading', { name: TITLE })).toHaveCount(0)

	// The unpublished event itself stays hidden from guests.
	const details = await page.request.get(
		`/api/method/lms.lms.utils.get_event_details?batch=${eventName}`
	)
	expect((await details.json()).message || {}).toEqual({})
	await context.close()
})

test('a logged-in learner registers through the link', async ({ browser }) => {
	const context = await browser.newContext()
	const page = await context.newPage()
	await login(page, STUDENT_EMAIL)
	await page.goto(linkUrl)
	await page.getByRole('button', { name: 'Register', exact: true }).click()

	// A learner with no license on file is asked for it first, then the
	// registration resumes on its own. One with a license goes straight in.
	const licenseDialog = page.getByRole('dialog').filter({ hasText: 'Add your professional license' })
	const landed = page.waitForURL(`**/lms/events/${eventName}`, { timeout: 30000 })
	const neededLicense = await licenseDialog
		.waitFor({ state: 'visible', timeout: 5000 })
		.then(() => true)
		.catch(() => false)
	if (neededLicense) {
		const fields = licenseDialog.getByTestId('license-fields')
		await fields.locator('select').selectOption('PT')
		await fields.getByPlaceholder('FL').fill('FL')
		await fields.locator('input').last().fill('PT99999')
		await licenseDialog.getByRole('button', { name: 'Save and continue' }).click()
	}
	await landed
	await expect(page.getByText(TITLE).first()).toBeVisible()

	await page.goto(linkUrl)
	await expect(page.getByTestId('private-join-registered')).toBeVisible()

	// Put the shared dev learner back the way it was found, so specs that
	// expect it to have no license keep working.
	if (neededLicense) {
		await api(page, 'frappe.client.set_value', {
			doctype: 'User',
			name: STUDENT_EMAIL,
			fieldname: JSON.stringify({
				license_type: '',
				license_state: '',
				professional_license_number: '',
			}),
		}).catch((e) => console.warn(`Could not clear the test license on ${STUDENT_EMAIL}: ${e}`))
	}
	await context.close()
})

test('a brand-new person creates an account through the link and lands registered', async ({
	browser,
}) => {
	// The prepaid-group case: no account yet, only the link. Uses a throwaway
	// signup-test+<stamp>@example.com account like e2e/signup-flow.spec.ts.
	const stamp = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
	const email = `signup-test+${stamp}@example.com`
	const context = await browser.newContext()
	const page = await context.newPage()
	await page.goto(linkUrl)
	await page.getByRole('button', { name: 'Create an account or log in to register' }).click()

	const dialog = page.getByRole('dialog')
	await dialog.getByLabel('Full name').fill('Signup Test Private Link')
	await dialog.getByLabel('Email').fill(email)
	await dialog.getByLabel('Password').fill(PASSWORD)
	const license = dialog.getByTestId('register-license-fields')
	await license.locator('select').selectOption('PT')
	await license.getByLabel('State').fill('FL')
	await license.getByLabel('License number').fill('PT-E2E-0002')
	await dialog.locator('button[type="submit"]').click()

	// Signup returns to the link with ?register=1, which registers them and
	// forwards to the event page without another click.
	await page.waitForURL(`**/lms/events/${eventName}`, { timeout: 30000 })
	await expect(page.getByText(TITLE).first()).toBeVisible()

	await page.goto(linkUrl)
	await expect(page.getByTestId('private-join-registered')).toBeVisible()
	await context.close()
})

test('admin enrolls a member from the Dashboard dialog', async ({ page }) => {
	await login(page, ADMIN_EMAIL)
	const result = await api(page, 'lms.lms.event_private_link.register_member', {
		event: eventName,
		member: ADMIN_EMAIL,
	})
	expect(result.status).toBe('registered')
	await page.goto(`/lms/events/${eventName}#dashboard`)
	await expect(page.getByText(STUDENT_EMAIL).or(page.getByText('Enrolled')).first()).toBeVisible()
})
