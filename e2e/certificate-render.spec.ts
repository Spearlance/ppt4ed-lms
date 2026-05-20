import { test, expect, Page } from '@playwright/test'

/**
 * CI gate for the Chromium-rendered Certificate print format.
 *
 * Three worst-case variants are minted as fixtures, downloaded as PDF,
 * and asserted to render to exactly one page. If any variant spills
 * onto page 2 the next deploy is blocked — that's the regression we're
 * paying for the Chromium switch to fix.
 *
 * Pre-reqs on dev:
 *   - Test admin (global-admin@test.com) exists with System Manager perms
 *   - Course slug "the-power-of-play..." exists with disciplines + instructors
 *   - Event slug "pediatric-adaptive-equipment..." exists with venue + instructors
 */

const ADMIN_EMAIL = 'global-admin@test.com'
const ADMIN_PASSWORD = 'TestUser@2026!'

const PAID_COURSE =
	'the-power-of-play-linking-play-to-language-cognitive-social-emotional-literacy-development'
const EVENT_NAME = 'pediatric-adaptive-equipment-evaluation-and-fitting'

async function loginAsAdmin(page: Page) {
	await page.goto('/login')
	await page.fill('#login_email', ADMIN_EMAIL)
	await page.fill('#login_password', ADMIN_PASSWORD)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function getCsrfToken(page: Page): Promise<string> {
	return await page.evaluate(() => (window as any).csrf_token as string)
}

async function insertCertificate(
	page: Page,
	csrf: string,
	fields: Record<string, unknown>,
): Promise<string> {
	const res = await page.request.post('/api/method/frappe.client.insert', {
		headers: { 'X-Frappe-CSRF-Token': csrf },
		data: {
			doc: {
				doctype: 'LMS Certificate',
				template: 'Certificate',
				member: ADMIN_EMAIL,
				issue_date: '2026-05-20',
				...fields,
			},
		},
	})
	expect(res.ok(), await res.text()).toBeTruthy()
	const body = await res.json()
	return body.message.name as string
}

async function deleteCertificate(page: Page, csrf: string, name: string) {
	await page.request.post('/api/method/frappe.client.delete', {
		headers: { 'X-Frappe-CSRF-Token': csrf },
		data: { doctype: 'LMS Certificate', name },
	})
}

async function downloadPdfPageCount(page: Page, certName: string): Promise<number> {
	const params = new URLSearchParams({
		doctype: 'LMS Certificate',
		name: certName,
		format: 'Certificate',
		no_letterhead: '1',
		pdf_generator: 'chrome',
	})
	const res = await page.request.get(
		`/api/method/frappe.utils.print_format.download_pdf?${params.toString()}`,
	)
	expect(res.ok(), await res.text()).toBeTruthy()
	const buf = await res.body()
	// %PDF- header check guards against the API returning a JSON error
	// payload with 200 OK (Frappe does this for some failure modes).
	expect(buf.subarray(0, 5).toString()).toBe('%PDF-')

	// Count /Type /Page entries, NOT /Pages. The Pages catalog object holds
	// the total but with `/Type /Pages` (plural); each leaf page is
	// `/Type /Page` followed by a non-letter byte. Negative lookahead via
	// regex avoids matching Pages.
	const pdfText = buf.toString('latin1')
	const matches = pdfText.match(/\/Type\s*\/Page(?![a-zA-Z])/g) ?? []
	return matches.length
}

test.describe('Certificate PDF render — one page guarantee', () => {
	test('tallest variant: license + ceu + paid course + 2 instructors', async ({ page }) => {
		await loginAsAdmin(page)
		const csrf = await getCsrfToken(page)
		const cert = await insertCertificate(page, csrf, {
			course: PAID_COURSE,
			license_info: 'License #12345 — State of Demoland — Renewal 2027',
			ceu_hours: 6,
		})
		try {
			const pages = await downloadPdfPageCount(page, cert)
			expect(pages).toBe(1)
		} finally {
			await deleteCertificate(page, csrf, cert)
		}
	})

	test('event variant: venue + dual logo + 2 instructors', async ({ page }) => {
		await loginAsAdmin(page)
		const csrf = await getCsrfToken(page)
		const cert = await insertCertificate(page, csrf, {
			event_name: EVENT_NAME,
			ceu_hours: 4,
		})
		try {
			const pages = await downloadPdfPageCount(page, cert)
			expect(pages).toBe(1)
		} finally {
			await deleteCertificate(page, csrf, cert)
		}
	})

	test('minimal variant: no license, no ceu, 1 instructor', async ({ page }) => {
		await loginAsAdmin(page)
		const csrf = await getCsrfToken(page)
		const cert = await insertCertificate(page, csrf, {
			course: PAID_COURSE,
		})
		try {
			const pages = await downloadPdfPageCount(page, cert)
			expect(pages).toBe(1)
		} finally {
			await deleteCertificate(page, csrf, cert)
		}
	})
})
