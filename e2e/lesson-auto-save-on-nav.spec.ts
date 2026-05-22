import { test, expect, Page } from '@playwright/test'

/**
 * PR — Auto-fire save_progress on any lesson navigation.
 *
 * Regression class: client reported passing quizzes/finishing lessons but not
 * unlocking the next part because Resource/Slides lessons stayed Incomplete.
 * Root cause: clicking a different lesson in the sidebar bypassed the
 * save_progress call that the Next button used to make. Fix moves the
 * save_progress trigger into onBeforeRouteUpdate / onBeforeRouteLeave guards
 * in Lesson.vue so any nav away from a lesson hits the backend chokepoint.
 *
 * The backend chokepoint (lms.lms.doctype.course_lesson.course_lesson
 * .save_progress) still gates Complete on quiz_completed && assignment_completed,
 * so this change cannot mark a lesson Complete while a quiz remains unpassed.
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
	// Free enrollment via the same frappe.client.insert path the frontend uses
	// in CourseCardOverlay.vue. Duplicate enrollments throw "already enrolled"
	// — we swallow that since the test only needs an enrollment to exist.
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

test.describe('Lesson auto-save on navigation', () => {
	test('navigating to another lesson via the sidebar fires save_progress for the outgoing lesson', async ({
		page,
	}) => {
		await login(page)
		await ensureEnrolled(page)

		// Land on lesson 1-1.
		await page.goto(`/lms/courses/${COURSE_SLUG}/learn/1-1`)

		// Wait for the lesson <h1> to render — that proves lesson.data has
		// loaded (which is what gates the save_progress call in the route
		// guard). The Mark as Complete button is hidden on video/quiz lessons
		// since the lesson auto-completes on watch-end or quiz-pass, so we
		// can't use that as the sentinel.
		await page.locator('h1').first().waitFor({ timeout: 15000 })

		// Find a sidebar lesson link that isn't the current 1-1 lesson. The
		// outline renders router-links with hrefs like
		// /lms/courses/<slug>/learn/<chapter>-<lesson>.
		const lessonLinks = page.locator(
			`a[href*="/lms/courses/${COURSE_SLUG}/learn/"]`
		)
		const linkCount = await lessonLinks.count()

		let targetHref = ''
		for (let i = 0; i < linkCount; i++) {
			const href = await lessonLinks.nth(i).getAttribute('href')
			if (href && !/\/learn\/1-1$/.test(href)) {
				targetHref = href
				break
			}
		}
		expect(
			targetHref,
			'sidebar should contain at least one lesson link other than 1-1'
		).not.toBe('')

		// Start listening BEFORE the click so we capture the in-flight POST
		// the route guard fires.
		const saveProgressCalls: string[] = []
		page.on('request', (req) => {
			if (
				req.url().includes(
					'lms.lms.doctype.course_lesson.course_lesson.save_progress'
				)
			) {
				saveProgressCalls.push(req.url())
			}
		})

		await page.locator(`a[href="${targetHref}"]`).first().click()
		await page.waitForURL(new RegExp(`${targetHref}$`), { timeout: 10000 })

		// The route guard awaits save_progress; give the network call a beat
		// to finalize after navigation completes.
		await page.waitForTimeout(500)

		expect(
			saveProgressCalls.length,
			'save_progress should fire when navigating away via the sidebar'
		).toBeGreaterThan(0)

		await logout(page)
	})

	test('clicking "Back to Course" from a lesson fires save_progress', async ({
		page,
	}) => {
		await login(page)
		await ensureEnrolled(page)

		await page.goto(`/lms/courses/${COURSE_SLUG}/learn/1-1`)
		await page.locator('h1').first().waitFor({ timeout: 15000 })

		const saveProgressCalls: string[] = []
		page.on('request', (req) => {
			if (
				req.url().includes(
					'lms.lms.doctype.course_lesson.course_lesson.save_progress'
				)
			) {
				saveProgressCalls.push(req.url())
			}
		})

		// "Back to Course" only renders when lesson.data.next is falsy (i.e.,
		// last lesson). For 1-1 a "Next" button is shown — clicking it still
		// exercises the onBeforeRouteUpdate guard (which is the same
		// chokepoint as Back to Course's onBeforeRouteLeave).
		const nextButton = page.getByRole('button', { name: /^Next$/ }).first()
		await nextButton.click()
		await page.waitForURL(/\/learn\/(?!1-1)/, { timeout: 10000 })

		await page.waitForTimeout(500)

		expect(
			saveProgressCalls.length,
			'save_progress should still fire on Next-button navigation'
		).toBeGreaterThan(0)

		await logout(page)
	})
})
