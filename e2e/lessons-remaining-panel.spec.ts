import { test, expect, Page } from '@playwright/test'

/**
 * PR — "Lessons remaining" panel on the course detail page.
 *
 * Surfaces an info panel listing incomplete lessons (with direct links) when
 * the viewer is enrolled in a course but hasn't finished it yet. Companion to
 * the auto-save-on-nav PR — helps users who got stuck on a locked quiz/
 * survey self-diagnose which lesson is blocking them.
 */

const STUDENT_EMAIL = 'pro@test.com'
const STUDENT_PASSWORD = 'TestUser@2026!'
const COURSE_SLUG =
	'the-power-of-play-linking-play-to-language-cognitive-social-emotional-literacy-development'

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

async function ensureEnrolled(page: Page) {
	const res = await api(page, 'frappe.client.insert', {
		doc: JSON.stringify({
			doctype: 'LMS Enrollment',
			course: COURSE_SLUG,
			member: STUDENT_EMAIL,
		}),
	})
	if (!res.ok()) {
		const body = await res.text()
		if (!/already enrolled/i.test(body)) {
			throw new Error(`Failed to enroll for test: ${body}`)
		}
	}
}

test.describe('Lessons remaining panel', () => {
	test('renders on course detail when enrolled and incomplete, with clickable lesson links', async ({
		page,
	}) => {
		await login(page)
		await ensureEnrolled(page)

		await page.goto(`/lms/courses/${COURSE_SLUG}`)

		// Scope all assertions to the panel itself — the page also renders a
		// full course outline below, which contains its own lesson links.
		const panel = page.locator('[data-testid="lessons-remaining-panel"]')
		await expect(panel).toBeVisible({ timeout: 15000 })
		await expect(panel).toContainText(
			/lesson\(s\) remaining to complete this course/i
		)

		// At least one unlocked lesson inside the panel as a router-link to a
		// /lms/courses/<slug>/learn/<n>-<n> route.
		const lessonLink = panel
			.locator(`a[href*="/lms/courses/${COURSE_SLUG}/learn/"]`)
			.first()
		await expect(lessonLink).toBeVisible({ timeout: 10000 })

		// Clicking the link should navigate to the lesson route.
		const href = await lessonLink.getAttribute('href')
		expect(href).toMatch(/\/learn\/\d+-\d+$/)
		await lessonLink.click()
		await page.waitForURL(new RegExp(`${href}$`), { timeout: 10000 })

		await logout(page)
	})
})
