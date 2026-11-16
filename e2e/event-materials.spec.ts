import { test, expect, Page } from '@playwright/test'
import path from 'path'

/**
 * Event materials on devlms.
 *
 * An admin uploads handouts on the event's Materials tab and names them; a
 * registered attendee opens them inside the LMS (PDF pages drawn in-page,
 * images inline) without a forced download. Unregistered visitors get nothing.
 *
 * Dev setup these tests assume (same as event-manual-certificates.spec.ts):
 *   - moderator-smoke@test.com / TestUser@2026! has the Moderator role
 *   - pro@test.com / TestUser@2026! is a plain learner
 *
 * Set MATERIALS_PDF / MATERIALS_IMAGE to absolute paths to try real files;
 * otherwise the tiny fixtures in e2e/fixtures are used.
 */

const PASSWORD = 'TestUser@2026!'
const SEED_EMAIL = 'moderator-smoke@test.com'
const STUDENT_EMAIL = 'pro@test.com'
const STAMP = Date.now().toString(36)
const TITLE = `E2E Materials ${STAMP}`
const PDF_FILE =
	process.env.MATERIALS_PDF || path.join(__dirname, 'fixtures', 'event-material.pdf')
const IMAGE_FILE =
	process.env.MATERIALS_IMAGE || path.join(__dirname, 'fixtures', 'event-material.png')
const SHOTS = process.env.MATERIALS_SHOTS || ''
const VIEW = '/api/method/lms.lms.event_materials.view_event_material'

test.describe.configure({ mode: 'serial' })
test.setTimeout(180000)

const ctx: { event?: string; pdf?: string } = {}
const leftovers: string[] = []

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

async function shot(page: Page, name: string) {
	if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`) })
}

async function addMaterial(page: Page, file: string, title: string) {
	await page.getByRole('button', { name: 'Add material' }).click()
	const dialog = page.getByRole('dialog')
	await expect(dialog).toBeVisible()
	await dialog.locator('input[type="file"]').setInputFiles(file)
	await expect(dialog.getByTestId('material-uploaded-name')).toBeVisible({ timeout: 120000 })
	// The name is suggested from the filename; the admin overrides it.
	const name = dialog.locator('input[type="text"]')
	await expect(name).not.toHaveValue('')
	await name.fill(title)
	await dialog.getByRole('button', { name: 'Add', exact: true }).click()
	await expect(dialog).toBeHidden({ timeout: 15000 })
	await expect(page.getByTestId('material-row').filter({ hasText: title })).toBeVisible()
}

/** True once the first PDF page canvas has real (non-blank) pixels. */
async function firstPageIsDrawn(page: Page) {
	return page.evaluate(() => {
		const canvas = document.querySelector(
			'[data-testid="pdf-viewer"] canvas'
		) as HTMLCanvasElement | null
		if (!canvas || !canvas.width || !canvas.height) return false
		const { data } = canvas
			.getContext('2d')!
			.getImageData(0, 0, canvas.width, canvas.height)
		for (let i = 0; i < data.length; i += 4) {
			// any pixel that is neither transparent nor pure white
			if (data[i + 3] !== 0 && (data[i] < 250 || data[i + 1] < 250 || data[i + 2] < 250)) {
				return true
			}
		}
		return false
	})
}

test.describe('Event materials', () => {
	test.beforeAll(async ({ browser }) => {
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)
		const day = yesterday()
		const doc = await insert(page, {
			doctype: 'LMS Event',
			title: TITLE,
			start_date: day,
			end_date: day,
			start_time: '09:00:00',
			end_time: '10:00:00',
			event_days: [{ date: day, start_time: '09:00:00', end_time: '10:00:00' }],
			timezone: 'America/New_York',
			description: 'E2E event materials',
			event_details: '<p>E2E event materials</p>',
			instructors: [{ instructor: SEED_EMAIL }],
			published: 1,
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
		if (!ctx.event) return
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)
		for (const name of await listNames(page, 'LMS Event Material', { event: ctx.event })) {
			await api(page, 'lms.lms.event_materials.delete_event_material', { name }).catch(() => {
				leftovers.push(`LMS Event Material: ${name}`)
			})
		}
		for (const name of await listNames(page, 'LMS Event Registration', { event: ctx.event })) {
			await tryDelete(page, 'LMS Event Registration', name)
		}
		await tryDelete(page, 'LMS Event', ctx.event)
		await page.close()
		if (leftovers.length) {
			console.warn(
				`event-materials: ${leftovers.length} fixture(s) could not be deleted. Sweep on dev:\n  ` +
					leftovers.join('\n  ')
			)
		}
	})

	test('admin uploads, names, renames and reorders materials', async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 })
		await login(page, SEED_EMAIL)
		await page.goto(`/lms/events/${ctx.event}#materials`)
		await expect(page.getByTestId('event-materials')).toBeVisible({ timeout: 15000 })
		await expect(page.getByText('No materials yet.')).toBeVisible()

		await addMaterial(page, PDF_FILE, 'Course slides')
		await addMaterial(page, IMAGE_FILE, 'Measurement table')

		// Rename the PDF.
		const pdfRow = page.getByTestId('material-row').filter({ hasText: 'Course slides' })
		await pdfRow.getByRole('button', { name: 'Rename' }).click()
		const dialog = page.getByRole('dialog')
		await dialog.locator('input[type="text"]').fill('Slideshow')
		await dialog.getByRole('button', { name: 'Save', exact: true }).click()
		await expect(dialog).toBeHidden()
		await expect(page.getByTestId('material-row').first()).toContainText('Slideshow')

		// Move the image above it, then back.
		await page
			.getByTestId('material-row')
			.filter({ hasText: 'Measurement table' })
			.getByRole('button', { name: 'Move up' })
			.click()
		await expect(page.getByTestId('material-row').first()).toContainText('Measurement table')
		await page
			.getByTestId('material-row')
			.filter({ hasText: 'Slideshow' })
			.getByRole('button', { name: 'Move up' })
			.click()
		await expect(page.getByTestId('material-row').first()).toContainText('Slideshow')

		const names = await listNames(page, 'LMS Event Material', { event: ctx.event, title: 'Slideshow' })
		expect(names).toHaveLength(1)
		ctx.pdf = names[0]
		await shot(page, 'admin-desktop')
	})

	test('attendee reads the PDF and image inside the LMS', async ({ page }) => {
		await page.setViewportSize({ width: 1440, height: 900 })
		let downloads = 0
		page.on('download', () => downloads++)

		await login(page, STUDENT_EMAIL)
		await page.goto(`/lms/events/${ctx.event}#dashboard`)
		await expect(page.getByTestId('materials-banner')).toBeVisible({ timeout: 15000 })
		await page.getByRole('button', { name: 'View materials' }).click()

		await expect(page.getByTestId('material-row')).toHaveCount(2)
		// Attendees get no management controls.
		await expect(page.getByRole('button', { name: 'Add material' })).toHaveCount(0)
		await expect(page.getByRole('button', { name: 'Rename' })).toHaveCount(0)

		// Desktop opens the first material straight away, drawn in-page.
		await expect(page.getByTestId('material-viewer')).toContainText('Slideshow')
		await expect.poll(() => firstPageIsDrawn(page), { timeout: 60000 }).toBe(true)
		await shot(page, 'attendee-desktop-pdf')

		await page.getByTestId('material-row').filter({ hasText: 'Measurement table' }).click()
		const image = page.getByTestId('material-viewer').locator('img')
		await expect(image).toBeVisible()
		await expect
			.poll(() => image.evaluate((el: HTMLImageElement) => el.naturalWidth), { timeout: 30000 })
			.toBeGreaterThan(0)
		await shot(page, 'attendee-desktop-image')

		// Served inline, not as an attachment.
		const res = await page.request.get(`${VIEW}?name=${ctx.pdf}`)
		expect(res.status()).toBe(200)
		expect(res.headers()['content-type']).toContain('application/pdf')
		expect(res.headers()['content-disposition']).toMatch(/^inline/)
		expect(downloads).toBe(0)
	})

	test('phone layout: list first, then the document, with a way back', async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 })
		await login(page, STUDENT_EMAIL)
		await page.goto(`/lms/events/${ctx.event}#materials`)
		await expect(page.getByTestId('material-row')).toHaveCount(2, { timeout: 15000 })
		await expect(page.getByTestId('material-viewer')).toHaveCount(0)
		await shot(page, 'attendee-phone-list')

		await page.getByTestId('material-row').filter({ hasText: 'Slideshow' }).click()
		await expect.poll(() => firstPageIsDrawn(page), { timeout: 60000 }).toBe(true)
		// The page fits the screen: no sideways scrolling to read a slide.
		const overflow = await page.evaluate(
			() => document.documentElement.scrollWidth - document.documentElement.clientWidth
		)
		expect(overflow).toBeLessThanOrEqual(1)
		await shot(page, 'attendee-phone-pdf')

		await page.getByRole('button', { name: 'Back to materials' }).click()
		await expect(page.getByTestId('material-row')).toHaveCount(2)
	})

	test('visitors who are not registered cannot open a material', async ({ browser }) => {
		const context = await browser.newContext()
		const res = await context.request.get(
			`${process.env.BASE_URL || 'https://devlms.ppt4ed.org'}${VIEW}?name=${ctx.pdf}`
		)
		expect(res.status()).toBe(403)
		await context.close()
	})
})
