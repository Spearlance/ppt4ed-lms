import { test, expect, Page } from '@playwright/test'

/**
 * PR — Course survey UX: Next/Submit + required questions.
 *
 * Client report (2026-05-19): every question on the course completion survey
 * showed "Submit" as its primary CTA, so users either submitted on question 1
 * (losing the rest) or stared at the pagination dots. Surveys also let users
 * advance with unanswered questions because the gate was wide open.
 *
 * Fix in Quiz.vue:
 *   - Template: drop `&& quiz.data.show_answers` from the Next-button gate so
 *     surveys (show_answers=false) get Next on every non-last question.
 *   - Handler: remove `if (!quiz.data.show_answers) return` from nextQuestion.
 *   - Add currentQuestionAnswered computed, disable Next/Submit until the
 *     current question has an answer.
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

test.describe('Course survey Next/Submit flow', () => {
	test('shows Next (not Submit) on non-last questions and gates buttons until answered', async ({
		page,
	}) => {
		await login(page)
		await ensureEnrolled(page)

		// Land on the course outline. Every certified course has a final
		// "Course Completion" chapter with a single "Course Survey" lesson
		// (see lms/patches/v2_0/attach_feedback_survey_to_certified_courses.py).
		await page.goto(`/lms/courses/${COURSE_SLUG}/learn/1-1`)

		// Find and click the survey lesson from the sidebar by visible text.
		// The text-based locator avoids hardcoding a chapter-lesson index that
		// drifts as courses gain/lose chapters.
		const surveyLink = page
			.locator(`a[href*="/lms/courses/${COURSE_SLUG}/learn/"]`, {
				hasText: /Course Survey/i,
			})
			.first()
		await surveyLink.waitFor({ timeout: 15000 })
		await surveyLink.click()

		// Wait for the quiz intro screen, then click into the survey.
		const startSurvey = page.getByRole('button', { name: /Start Survey/i })
		await startSurvey.waitFor({ timeout: 15000 })
		await startSurvey.click()

		// Question 1 is a Choices question (Therapy Discipline).
		const nextButton = page.getByRole('button', { name: /^Next$/ })
		const submitButton = page.getByRole('button', { name: /^Submit$/ })

		// REGRESSION GATE: on question 1, the CTA must be Next, not Submit.
		await expect(nextButton).toBeVisible()
		await expect(submitButton).toHaveCount(0)

		// REQUIRED GATE: Next is disabled until the user picks a radio.
		await expect(nextButton).toBeDisabled()
		await page.locator('input[type="radio"]').first().check()
		await expect(nextButton).toBeEnabled()

		await nextButton.click()

		// Subsequent questions are Open Ended (TextEditor) — Next stays
		// disabled until something is typed into the editor.
		await expect(nextButton).toBeDisabled()

		// Walk to the last question. The seed has 8 questions; click Next as
		// many times as we have non-last questions. After Q1 we're on Q2, so
		// there are 6 more Next clicks before Q8.
		const fillCurrentOpenEnded = async () => {
			// TextEditor renders a contenteditable. FormControl (textarea/text)
			// is also possible. Try contenteditable first.
			const editor = page.locator('[contenteditable="true"]').first()
			if (await editor.count()) {
				await editor.click()
				await editor.fill('test response')
				return
			}
			const textarea = page.locator('textarea').first()
			if (await textarea.count()) {
				await textarea.fill('test response')
				return
			}
			throw new Error('No input found for current open-ended question')
		}

		for (let i = 0; i < 6; i++) {
			await fillCurrentOpenEnded()
			await expect(nextButton).toBeEnabled()
			await nextButton.click()
			// New question loaded → button is disabled again.
			await expect(nextButton).toBeDisabled()
		}

		// We should now be on the LAST question. CTA flips from Next to Submit.
		await expect(nextButton).toHaveCount(0)
		await expect(submitButton).toBeVisible()
		await expect(submitButton).toBeDisabled()

		await fillCurrentOpenEnded()
		await expect(submitButton).toBeEnabled()

		// Do not actually click Submit — we don't want to pollute Quiz
		// Submissions with junk from CI. The button-state gate is the
		// regression we're fixing; submission happens in the existing
		// graded-quiz e2e flows.

		await logout(page)
	})
})
