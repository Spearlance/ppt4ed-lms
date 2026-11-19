import { test, expect, Page } from '@playwright/test'

/**
 * Cancelling an event on devlms.
 *
 * An admin cancels an event from its Settings tab, choosing whether to email
 * the registered attendees. The attendee still sees the event, with a
 * cancelled notice. Restoring removes the notice and leaves it unpublished.
 *
 * The event is created by this spec, unpublished, with one registration
 * (pro@test.com, an internal test account, the only address ever emailed).
 *
 * Dev setup: moderator-smoke@test.com (Moderator) and pro@test.com (learner),
 * both with password TestUser@2026!
 */

const PASSWORD = 'TestUser@2026!'
const SEED_EMAIL = 'moderator-smoke@test.com'
const STUDENT_EMAIL = 'pro@test.com'
const STAMP = Date.now().toString(36)
const NOTE = `Venue unavailable ${STAMP}`

test.describe.configure({ mode: 'serial' })
test.setTimeout(120000)

const ctx: { event?: string } = {}

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

async function eventState(page: Page) {
	return api(page, 'frappe.client.get_value', {
		doctype: 'LMS Event',
		filters: JSON.stringify({ name: ctx.event }),
		fieldname: JSON.stringify(['cancelled', 'published', 'cancellation_message']),
	})
}

function nextMonth() {
	const d = new Date()
	d.setDate(d.getDate() + 30)
	return d.toISOString().slice(0, 10)
}

async function openCancelDialog(page: Page) {
	await page.goto(`/lms/events/${ctx.event}#settings`)
	await page.getByRole('button', { name: 'Cancel event', exact: true }).click()
	const dialog = page.getByRole('dialog')
	await expect(dialog.getByTestId('cancel-registrations')).toHaveText(
		'1 person is registered for this event.',
		{ timeout: 15000 }
	)
	return dialog
}

test.describe('Cancel event', () => {
	test.beforeAll(async ({ browser }) => {
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)
		const day = nextMonth()
		const doc = await insert(page, {
			doctype: 'LMS Event',
			title: `E2E Cancel ${STAMP}`,
			start_date: day,
			end_date: day,
			start_time: '09:00:00',
			end_time: '10:00:00',
			event_days: [{ date: day, start_time: '09:00:00', end_time: '10:00:00' }],
			timezone: 'America/New_York',
			description: 'E2E cancel event',
			event_details: '<p>E2E cancel event</p>',
			instructors: [{ instructor: SEED_EMAIL }],
			published: 0,
		})
		ctx.event = doc.name
		await insert(page, {
			doctype: 'LMS Event Registration',
			event: doc.name,
			member: STUDENT_EMAIL,
		})
		await page.close()
	})

	test.afterAll(async ({ browser }) => {
		// Remove only this spec's own fixture.
		if (!ctx.event) return
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)
		const rows = await api(page, 'frappe.client.get_list', {
			doctype: 'LMS Event Registration',
			filters: JSON.stringify({ event: ctx.event }),
			fields: JSON.stringify(['name']),
		})
		for (const row of rows || []) {
			await api(page, 'frappe.client.delete', {
				doctype: 'LMS Event Registration',
				name: row.name,
			}).catch(() => {})
		}
		await api(page, 'lms.lms.api.delete_event', { event: ctx.event }).catch((e) => {
			console.warn(`event-cancel: could not remove fixture ${ctx.event}: ${e}`)
		})
		await page.close()
	})

	test('admin cancels without emailing anyone', async ({ page }) => {
		await login(page, SEED_EMAIL)
		const dialog = await openCancelDialog(page)

		// Email is opt-in every time.
		const notify = dialog.getByTestId('cancel-notify')
		await expect(notify).not.toBeChecked()
		await expect(dialog.getByText('No email will be sent.')).toBeVisible()
		await dialog.locator('textarea').fill(NOTE)
		await dialog.getByRole('button', { name: 'Cancel event', exact: true }).click()

		await expect(page.getByText('Event cancelled. No email was sent.').first()).toBeVisible({
			timeout: 15000,
		})
		await expect(page.getByTestId('event-cancelled-settings')).toBeVisible()
		await expect(page.getByTestId('event-cancelled-banner')).toContainText(NOTE)
		const state = await eventState(page)
		expect(state.cancelled).toBe(1)
		expect(state.published).toBe(0)
	})

	test('the registered attendee still sees the event, marked cancelled', async ({ page }) => {
		await login(page, STUDENT_EMAIL)
		await page.goto(`/lms/events/${ctx.event}`)
		const banner = page.getByTestId('event-cancelled-banner')
		await expect(banner).toBeVisible({ timeout: 15000 })
		await expect(banner).toContainText('This event has been cancelled')
		await expect(banner).toContainText(NOTE)
	})

	test('a cancelled event cannot be deleted or published, and can be restored', async ({ page }) => {
		await login(page, SEED_EMAIL)
		await page.goto(`/lms/events/${ctx.event}#settings`)
		await expect(page.getByTestId('event-cancelled-settings')).toBeVisible({ timeout: 15000 })
		await expect(page.getByRole('button', { name: 'Cancel event', exact: true })).toHaveCount(0)

		await page.getByRole('button', { name: 'Restore event' }).click()
		await page.getByRole('dialog').getByRole('button', { name: 'Restore event' }).click()
		await expect(page.getByText('Event restored. It is still unpublished.').first()).toBeVisible({
			timeout: 15000,
		})
		await expect(page.getByTestId('event-cancelled-settings')).toHaveCount(0)
		await expect(page.getByTestId('event-cancelled-banner')).toHaveCount(0)
		const state = await eventState(page)
		expect(state.cancelled).toBe(0)
		expect(state.published).toBe(0)
	})

	test('admin cancels and emails the registered attendee', async ({ page }) => {
		await login(page, SEED_EMAIL)
		const dialog = await openCancelDialog(page)
		await dialog.getByTestId('cancel-notify').check()
		await expect(dialog.getByText('1 person will be emailed as soon as you confirm.')).toBeVisible()
		await dialog.getByRole('button', { name: 'Cancel event and send email' }).click()

		await expect(page.getByText('Event cancelled. 1 attendee emailed.').first()).toBeVisible({
			timeout: 15000,
		})
		expect((await eventState(page)).cancelled).toBe(1)
	})
})
