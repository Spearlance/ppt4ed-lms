import { test, expect, Page } from '@playwright/test'

/**
 * Bonus chapter behavior:
 *   - `is_bonus=1` on a Course Chapter is surfaced on the get_course_outline API.
 *   - A bonus chapter's lessons stay unlocked for non-enrolled students even
 *     though the prior chapter is incomplete (chapter-gating bypass).
 *
 * Setup uses global-admin@test.com to flip the flag via frappe.client.set_value,
 * then verifies as pro@test.com (not enrolled in CATCH_THE_WAVE on devlms).
 * Always restores the original is_bonus value so the test is idempotent.
 */

const ADMIN_EMAIL = 'global-admin@test.com'
const ADMIN_PASSWORD = 'TestUser@2026!'
const STUDENT_EMAIL = 'pro@test.com'
const STUDENT_PASSWORD = 'TestUser@2026!'
const COURSE_SLUG =
	'catch-the-wave-introduction-to-whole-body-vibration-in-pediatric-therapy-for-pts-ots-and-slps'

async function loginAs(page: Page, email: string, password: string) {
	await page.goto('/login')
	await page.fill('#login_email', email)
	await page.fill('#login_password', password)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function setValue(
	page: Page,
	doctype: string,
	name: string,
	field: string,
	value: number | string
) {
	const csrf = await page.evaluate(() => (window as any).csrf_token as string)
	const res = await page.request.post('/api/method/frappe.client.set_value', {
		headers: { 'X-Frappe-CSRF-Token': csrf },
		data: { doctype, name, fieldname: field, value },
	})
	if (!res.ok()) {
		throw new Error(`set_value failed: ${await res.text()}`)
	}
}

test.describe('Bonus chapter', () => {
	test('is surfaced on the outline and unlocks its lessons for incomplete students', async ({
		browser,
	}) => {
		const adminCtx = await browser.newContext()
		const adminPage = await adminCtx.newPage()
		await loginAs(adminPage, ADMIN_EMAIL, ADMIN_PASSWORD)

		const outlineRes = await adminPage.request.get(
			`/api/method/lms.lms.utils.get_course_outline?course=${COURSE_SLUG}&progress=false`
		)
		expect(outlineRes.ok()).toBeTruthy()
		const chapters = (await outlineRes.json()).message
		expect(Array.isArray(chapters)).toBeTruthy()
		expect(chapters.length).toBeGreaterThan(1)

		// Pick the second chapter — it naturally locks for non-enrolled students
		// (chapter 1 won't be complete), so flipping is_bonus is observable.
		const targetChapter = chapters[1]
		const originalBonus = targetChapter.is_bonus ?? 0

		try {
			await setValue(adminPage, 'Course Chapter', targetChapter.name, 'is_bonus', 1)

			// Verify from a separate non-admin context (no can_modify_course bypass).
			const studentCtx = await browser.newContext()
			const studentPage = await studentCtx.newPage()
			await loginAs(studentPage, STUDENT_EMAIL, STUDENT_PASSWORD)

			const studentOutlineRes = await studentPage.request.get(
				`/api/method/lms.lms.utils.get_course_outline?course=${COURSE_SLUG}&progress=true`
			)
			expect(studentOutlineRes.ok()).toBeTruthy()
			const studentChapters = (await studentOutlineRes.json()).message
			const studentTarget = studentChapters.find(
				(c: any) => c.name === targetChapter.name
			)
			expect(studentTarget).toBeDefined()
			expect(studentTarget.is_bonus).toBe(1)
			expect(studentTarget.is_locked).toBeFalsy()
			for (const lesson of studentTarget.lessons || []) {
				expect(
					lesson.is_locked,
					`bonus chapter lesson "${lesson.title}" should not be locked`
				).toBeFalsy()
			}

			await studentCtx.close()
		} finally {
			await setValue(
				adminPage,
				'Course Chapter',
				targetChapter.name,
				'is_bonus',
				originalBonus
			)
			await adminCtx.close()
		}
	})
})
