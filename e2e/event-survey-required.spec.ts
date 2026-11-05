import { test, expect, Page } from '@playwright/test'

/**
 * "Require survey for course credit" + the admin sample certificate preview.
 *
 * Two Online Quiz events are seeded on devlms:
 *   - required: survey_quiz attached, require_survey_for_credit = 1
 *       quiz pass alone must NOT certify; survey afterwards does
 *   - optional: survey_quiz attached, require_survey_for_credit = 0
 *       quiz pass alone certifies; the survey is optional feedback
 *
 * Then a Global Admin opens the sample certificate preview for the required
 * event (watermarked, nothing issued) and a learner is refused.
 *
 * Dev setup assumed (same as event-credit-verification.spec.ts):
 *   - moderator-smoke@test.com / TestUser@2026! (Moderator) seeds fixtures
 *   - global-admin@test.com / TestUser@2026! (Global Admin) previews
 *   - pro@test.com / TestUser@2026! is the learner
 *   - The shared "Course Survey" quiz (is_survey=1) exists
 */

const PASSWORD = 'TestUser@2026!'
const SEED_EMAIL = 'moderator-smoke@test.com'
const ADMIN_EMAIL = 'global-admin@test.com'
const STUDENT_EMAIL = 'pro@test.com'
const STAMP = Date.now().toString(36)
const TITLE_PREFIX = `Garrett Test Survey Required ${STAMP}`

test.describe.configure({ mode: 'serial' })
test.setTimeout(120000)

type Answer = { question_name: string; answer: string[]; type: string }
type Ctx = {
	surveyQuiz: string
	surveyAnswers: Answer[]
	question: string
	creditQuiz: string
	quizAnswers: Answer[]
	requiredEvent: string
	optionalEvent: string
}
const ctx: Partial<Ctx> = {}

async function login(page: Page, email: string) {
	await page.goto('/login')
	await page.fill('#login_email', email)
	await page.fill('#login_password', PASSWORD)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function logout(page: Page) {
	await page.goto('/api/method/logout')
	await page.waitForLoadState('networkidle').catch(() => {})
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

const leftovers: string[] = []

async function tryDelete(page: Page, doctype: string, name: string) {
	await api(page, 'frappe.client.delete', { doctype, name }).catch(() => {
		leftovers.push(`${doctype}: ${name}`)
	})
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

async function countCertificates(page: Page, event: string) {
	return (await listNames(page, 'LMS Certificate', { event_name: event })).length
}

function yesterday() {
	const d = new Date()
	d.setDate(d.getDate() - 1)
	return d.toISOString().slice(0, 10)
}

async function makeEvent(page: Page, suffix: string, requireSurvey: 0 | 1) {
	const day = yesterday()
	const doc = await insert(page, {
		doctype: 'LMS Event',
		title: `${TITLE_PREFIX} ${suffix}`,
		start_date: day,
		end_date: day,
		start_time: '09:00:00',
		end_time: '10:00:00',
		event_days: [{ date: day, start_time: '09:00:00', end_time: '10:00:00' }],
		timezone: 'America/New_York',
		description: 'Garrett Test survey-required event',
		event_details: '<p>Garrett Test survey-required event</p>',
		instructors: [{ instructor: SEED_EMAIL }],
		certification: 1,
		credit_hours: 1,
		event_type: 'Live Webinar',
		credit_verification: 'Online Quiz',
		credit_quiz: ctx.creditQuiz,
		survey_quiz: ctx.surveyQuiz,
		require_survey_for_credit: requireSurvey,
		show_signer_credentials: 1,
		published: 1,
	})
	await insert(page, {
		doctype: 'LMS Event Registration',
		event: doc.name,
		member: STUDENT_EMAIL,
	})
	return doc.name as string
}

/** Learners can't read LMS Question, so the moderator precomputes answers. */
async function buildAnswers(adminPage: Page, quizName: string): Promise<Answer[]> {
	const quiz = await api(adminPage, 'frappe.client.get', { doctype: 'LMS Quiz', name: quizName })
	const results: Answer[] = []
	for (const row of quiz.questions || []) {
		const q = await api(adminPage, 'frappe.client.get', {
			doctype: 'LMS Question',
			name: row.question,
		})
		const answer = q.type === 'Choices' ? [q.option_1] : ['e2e response']
		results.push({ question_name: row.question, answer, type: q.type })
	}
	return results
}

test.describe('Require survey for course credit', () => {
	test.beforeAll(async ({ browser }) => {
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)

		const surveys = await listNames(page, 'LMS Quiz', { is_survey: 1, title: 'Course Survey' })
		if (!surveys.length) throw new Error('Shared "Course Survey" quiz not found on dev')
		ctx.surveyQuiz = surveys[0]
		ctx.surveyAnswers = await buildAnswers(page, ctx.surveyQuiz)

		const question = await insert(page, {
			doctype: 'LMS Question',
			question: `${TITLE_PREFIX} — Is this the credit quiz?`,
			type: 'Choices',
			option_1: 'Yes',
			is_correct_1: 1,
			option_2: 'No',
			is_correct_2: 0,
			multiple: 0,
		})
		ctx.question = question.name
		const quiz = await insert(page, {
			doctype: 'LMS Quiz',
			title: `${TITLE_PREFIX} Credit Quiz`,
			passing_percentage: 80,
			max_attempts: 3,
			show_answers: 0,
			questions: [{ question: question.name, marks: 1 }],
		})
		ctx.creditQuiz = quiz.name
		ctx.quizAnswers = await buildAnswers(page, ctx.creditQuiz)

		ctx.requiredEvent = await makeEvent(page, 'Required', 1)
		ctx.optionalEvent = await makeEvent(page, 'Optional', 0)
		await page.close()
	})

	test.afterAll(async ({ browser }) => {
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)
		const events = [ctx.requiredEvent, ctx.optionalEvent].filter(Boolean) as string[]
		for (const event of events) {
			for (const doctype of ['LMS Certificate', 'LMS Quiz Submission']) {
				for (const name of await listNames(page, doctype, { event_name: event })) {
					await tryDelete(page, doctype, name)
				}
			}
			for (const name of await listNames(page, 'LMS Event Registration', { event })) {
				await tryDelete(page, 'LMS Event Registration', name)
			}
			await tryDelete(page, 'LMS Event', event)
		}
		if (ctx.creditQuiz) await tryDelete(page, 'LMS Quiz', ctx.creditQuiz)
		if (ctx.question) await tryDelete(page, 'LMS Question', ctx.question)
		await page.close()
		if (leftovers.length) {
			console.warn(
				`event-survey-required: ${leftovers.length} fixture(s) could not be deleted. Sweep on dev:\n  ` +
					leftovers.join('\n  ')
			)
		}
	})

	test('required: quiz pass alone does not certify, survey afterwards does, exactly once', async ({
		page,
	}) => {
		await login(page, STUDENT_EMAIL)
		const event = ctx.requiredEvent!

		const quiz = await api(page, 'lms.lms.api.submit_event_quiz', {
			event,
			results: JSON.stringify(ctx.quizAnswers),
		})
		expect(quiz.pass).toBeTruthy()
		expect(quiz.certificate).toBeNull()
		expect(await countCertificates(page, event)).toBe(0)

		// Learner sees the quiz passed and the survey still pending (mobile width).
		await page.setViewportSize({ width: 390, height: 844 })
		await page.goto(`/lms/events/${event}#dashboard`)
		const progress = page.getByTestId('credit-progress')
		await expect(progress).toBeVisible({ timeout: 15000 })
		await expect(progress).toContainText('Passed')
		await expect(progress).toContainText('Feedback survey')
		await expect(progress).not.toContainText('(optional)')
		await expect(page.getByText('Submit your feedback to receive your certificate')).toBeVisible()
		await page.screenshot({ path: 'test-results/event-survey-required-mobile.png', fullPage: true })

		const survey = await api(page, 'lms.lms.api.submit_event_survey', {
			event,
			results: JSON.stringify(ctx.surveyAnswers),
		})
		expect(survey.certificate).toBeTruthy()
		expect(await countCertificates(page, event)).toBe(1)

		// A second quiz pass never duplicates the award.
		const again = await api(page, 'lms.lms.api.submit_event_quiz', {
			event,
			results: JSON.stringify(ctx.quizAnswers),
		})
		expect(again.certificate).toBeNull()
		expect(await countCertificates(page, event)).toBe(1)

		await page.setViewportSize({ width: 1280, height: 800 })
		await page.goto(`/lms/events/${event}#dashboard`)
		await expect(page.getByTestId('credit-progress')).toContainText('Issued', { timeout: 15000 })
		await logout(page)
	})

	test('optional: quiz pass alone certifies and the survey is labelled optional', async ({
		page,
	}) => {
		await login(page, STUDENT_EMAIL)
		const event = ctx.optionalEvent!

		await page.goto(`/lms/events/${event}#dashboard`)
		const progress = page.getByTestId('credit-progress')
		await expect(progress).toBeVisible({ timeout: 15000 })
		await expect(progress).toContainText('Feedback survey (optional)')

		const quiz = await api(page, 'lms.lms.api.submit_event_quiz', {
			event,
			results: JSON.stringify(ctx.quizAnswers),
		})
		expect(quiz.pass).toBeTruthy()
		expect(quiz.certificate).toBeTruthy()
		expect(await countCertificates(page, event)).toBe(1)
		await logout(page)
	})

	test('admin preview is a watermarked sample that issues nothing', async ({ page }) => {
		await login(page, ADMIN_EMAIL)
		const event = ctx.requiredEvent!
		const before = await countCertificates(page, event)

		await page.goto(`/lms/events/${event}#dashboard`)
		await page.getByRole('link', { name: 'Preview certificate' }).click()
		await page.waitForURL(`**/admin/certificate-preview/event/${event}`)
		await expect(page.getByTestId('sample-preview-banner')).toBeVisible({ timeout: 15000 })

		const frame = page.frameLocator('[data-testid="sample-preview-frame"]')
		await expect(frame.locator('.cert-sample-watermark')).toHaveText('SAMPLE', { timeout: 15000 })
		await expect(frame.locator('.cert-recipient-name')).toHaveText('Sample Participant')
		await expect(frame.locator('.cert-format')).toHaveText('Live Course')
		await expect(frame.locator('.cert-sig-name').first()).toBeVisible()
		await page.screenshot({ path: 'test-results/event-certificate-preview.png', fullPage: true })

		const pdf = await page.request.get(
			`/api/method/lms.lms.ceu_event_admin.preview_event_certificate_pdf?event=${encodeURIComponent(event)}`
		)
		expect(pdf.ok(), await pdf.text().catch(() => '')).toBeTruthy()
		const buf = await pdf.body()
		expect(buf.subarray(0, 5).toString()).toBe('%PDF-')
		const pages = (buf.toString('latin1').match(/\/Type\s*\/Page(?![a-zA-Z])/g) ?? []).length
		expect(pages).toBe(1)

		expect(await countCertificates(page, event)).toBe(before)
		await logout(page)
	})

	test('learner cannot preview certificates', async ({ page }) => {
		await login(page, STUDENT_EMAIL)
		const event = ctx.requiredEvent!
		const res = await page.request.get(
			`/api/method/lms.lms.ceu_event_admin.preview_event_certificate?event=${encodeURIComponent(event)}`
		)
		expect(res.status()).toBe(403)

		await page.goto(`/lms/admin/certificate-preview/event/${event}`)
		await expect(page.getByTestId('sample-preview-error')).toBeVisible({ timeout: 15000 })
		await logout(page)
	})
})
