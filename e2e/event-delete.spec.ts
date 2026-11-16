import { test, expect, Page } from '@playwright/test'

/**
 * Guarded event delete on devlms.
 *
 * The Delete button in event Settings must refuse an event that has
 * registrations (and leave it untouched), and must remove an empty one.
 * Both events are created by this spec; no other event is ever targeted.
 *
 * Dev setup: moderator-smoke@test.com (Moderator) and pro@test.com (learner),
 * both with password TestUser@2026!
 */

const PASSWORD = 'TestUser@2026!'
const SEED_EMAIL = 'moderator-smoke@test.com'
const STUDENT_EMAIL = 'pro@test.com'
const STAMP = Date.now().toString(36)

test.describe.configure({ mode: 'serial' })
test.setTimeout(120000)

const ctx: { registered?: string; empty?: string } = {}

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

async function insert(page: Page, doc: Record<string, unknown>) {
	return api(page, 'frappe.client.insert', { doc: JSON.stringify(doc) })
}

async function exists(page: Page, doctype: string, filters: Record<string, unknown>) {
	const rows = await api(page, 'frappe.client.get_list', {
		doctype,
		filters: JSON.stringify(filters),
		fields: JSON.stringify(['name']),
		limit_page_length: 5,
	})
	return (rows || []).length
}

function nextMonth() {
	const d = new Date()
	d.setDate(d.getDate() + 30)
	return d.toISOString().slice(0, 10)
}

async function makeEvent(page: Page, title: string) {
	const day = nextMonth()
	const doc = await insert(page, {
		doctype: 'LMS Event',
		title,
		start_date: day,
		end_date: day,
		start_time: '09:00:00',
		end_time: '10:00:00',
		event_days: [{ date: day, start_time: '09:00:00', end_time: '10:00:00' }],
		timezone: 'America/New_York',
		description: 'E2E guarded delete',
		event_details: '<p>E2E guarded delete</p>',
		instructors: [{ instructor: SEED_EMAIL }],
		published: 0,
	})
	return doc.name as string
}

async function clickDelete(page: Page, event: string) {
	await page.goto(`/lms/events/${event}#settings`)
	// The trash button sits next to Save in the header on the Settings tab.
	const save = page.getByRole('button', { name: 'Save', exact: true })
	await expect(save).toBeVisible({ timeout: 15000 })
	await save.locator('xpath=preceding-sibling::button[1]').click()
	const dialog = page.getByRole('dialog')
	await expect(dialog).toContainText('cannot be deleted')
	await dialog.getByRole('button', { name: 'Delete', exact: true }).click()
}

test.describe('Guarded event delete', () => {
	test.beforeAll(async ({ browser }) => {
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)
		ctx.registered = await makeEvent(page, `E2E Delete Registered ${STAMP}`)
		ctx.empty = await makeEvent(page, `E2E Delete Empty ${STAMP}`)
		await insert(page, {
			doctype: 'LMS Event Registration',
			event: ctx.registered,
			member: STUDENT_EMAIL,
		})
		await page.close()
	})

	test.afterAll(async ({ browser }) => {
		// Remove only this spec's own registered fixture.
		if (!ctx.registered) return
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)
		const rows = await api(page, 'frappe.client.get_list', {
			doctype: 'LMS Event Registration',
			filters: JSON.stringify({ event: ctx.registered }),
			fields: JSON.stringify(['name']),
		})
		for (const row of rows || []) {
			await api(page, 'frappe.client.delete', {
				doctype: 'LMS Event Registration',
				name: row.name,
			}).catch(() => {})
		}
		await api(page, 'lms.lms.api.delete_event', { event: ctx.registered }).catch((e) => {
			console.warn(`event-delete: could not remove fixture ${ctx.registered}: ${e}`)
		})
		// The empty fixture is normally gone already; sweep it if a test bailed early.
		if (ctx.empty && (await exists(page, 'LMS Event', { name: ctx.empty }))) {
			await api(page, 'lms.lms.api.delete_event', { event: ctx.empty }).catch(() => {})
		}
		await page.close()
	})

	test('an event with registrations is refused and left intact', async ({ page }) => {
		await login(page, SEED_EMAIL)
		await clickDelete(page, ctx.registered!)
		await expect(
			page.getByText(/cannot be deleted because it has 1 registered attendee/).first()
		).toBeVisible({ timeout: 15000 })
		expect(await exists(page, 'LMS Event', { name: ctx.registered })).toBe(1)
		expect(await exists(page, 'LMS Event Registration', { event: ctx.registered })).toBe(1)
	})

	test('an empty event is deleted', async ({ page }) => {
		await login(page, SEED_EMAIL)
		await clickDelete(page, ctx.empty!)
		await expect(page.getByText('Event deleted successfully').first()).toBeVisible({ timeout: 15000 })
		await page.waitForURL('**/lms/events', { timeout: 15000 })
		expect(await exists(page, 'LMS Event', { name: ctx.empty })).toBe(0)
	})
})
