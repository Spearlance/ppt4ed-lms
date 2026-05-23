import { test, expect, Page } from '@playwright/test'

/**
 * Bottom Course Outline shows a green check on completed lessons. The
 * separate "Lessons remaining" panel that used to sit above the outline was
 * removed in the same change — assert it's gone post-deploy so it doesn't
 * sneak back in via a cached chunk.
 *
 * Fixture: pro@test.com is already enrolled in the free IEP-2 course on
 * devlms, so no enrollment step is required.
 */

const STUDENT_EMAIL = 'pro@test.com'
const STUDENT_PASSWORD = 'TestUser@2026!'
const COURSE_SLUG = 'navigating-the-iep-process-in-florida-schools-2'
const LESSON_TITLE = 'Advocating for your child at IEP Meetings'

async function login(page: Page) {
	await page.goto('/login')
	await page.fill('#login_email', STUDENT_EMAIL)
	await page.fill('#login_password', STUDENT_PASSWORD)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function logout(page: Page) {
	await page.goto('/api/method/logout')
	await page.waitForLoadState('networkidle').catch(() => {})
}

async function api(page: Page, method: string, data: Record<string, unknown>) {
	const csrf = await page.evaluate(() => (window as any).csrf_token as string)
	return page.request.post(`/api/method/${method}`, {
		headers: { 'X-Frappe-CSRF-Token': csrf },
		data,
	})
}

async function ensureLessonComplete(page: Page, lessonName: string) {
	// LMS Course Progress has no unique constraint on (course, member, lesson),
	// so check before inserting — otherwise duplicate rows accumulate across
	// test runs.
	const filters = encodeURIComponent(
		JSON.stringify({
			course: COURSE_SLUG,
			member: STUDENT_EMAIL,
			lesson: lessonName,
			status: 'Complete',
		})
	)
	const listRes = await page.request.get(
		`/api/method/frappe.client.get_list?doctype=LMS Course Progress&filters=${filters}&fields=["name"]&limit=1`
	)
	if (listRes.ok()) {
		const existing = (await listRes.json()).message || []
		if (existing.length > 0) return
	}

	const res = await api(page, 'frappe.client.insert', {
		doc: JSON.stringify({
			doctype: 'LMS Course Progress',
			course: COURSE_SLUG,
			member: STUDENT_EMAIL,
			lesson: lessonName,
			status: 'Complete',
		}),
	})
	if (!res.ok()) {
		throw new Error(`Failed to mark lesson complete: ${await res.text()}`)
	}
}

async function setupCompletedLesson(page: Page) {
	await login(page)

	const outlineRes = await page.request.get(
		`/api/method/lms.lms.utils.get_course_outline?course=${COURSE_SLUG}&progress=true`
	)
	expect(outlineRes.ok()).toBeTruthy()
	const chapters = (await outlineRes.json()).message
	expect(Array.isArray(chapters)).toBeTruthy()
	expect(chapters.length).toBeGreaterThan(0)
	expect(chapters[0].lessons.length).toBeGreaterThan(0)

	const firstLesson = chapters[0].lessons[0]
	await ensureLessonComplete(page, firstLesson.name)
	return firstLesson
}

test.describe('Course outline lesson-completion check', () => {
	// Two independent tests so the checkmark assertion (verifying wiring that
	// already exists on devlms) can pass before the panel-removal change has
	// been deployed.

	test('green check renders next to a completed lesson in the bottom outline', async ({
		page,
	}) => {
		await setupCompletedLesson(page)

		await page.goto(`/lms/courses/${COURSE_SLUG}`)

		const outlineHeading = page.getByText(/^Course Outline$/).first()
		await expect(outlineHeading).toBeVisible({ timeout: 15000 })

		// Chapter 1 is open by default — find the lesson row by its title and
		// assert a green-700 check icon sits inside it.
		const lessonRow = page
			.locator('.outline-lesson')
			.filter({ hasText: LESSON_TITLE })
			.first()
		await expect(lessonRow).toBeVisible({ timeout: 10000 })

		const greenCheck = lessonRow.locator('svg.text-green-700')
		await expect(greenCheck).toBeVisible({ timeout: 5000 })

		await logout(page)
	})

	test('removed remaining-lessons panel does not render (post-deploy)', async ({
		page,
	}) => {
		await setupCompletedLesson(page)
		await page.goto(`/lms/courses/${COURSE_SLUG}`)

		await expect(
			page.locator('[data-testid="lessons-remaining-panel"]')
		).toHaveCount(0)

		await logout(page)
	})
})
