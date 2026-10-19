import { test, expect, Page } from '@playwright/test'

/**
 * Event CEU credit verification on devlms.
 *
 * Three ways an event can issue its certificate (LMS Event.credit_verification):
 *   - Survey Only    — feedback survey alone mints the cert (pre-existing flow)
 *   - Online Quiz    — survey + pass the linked quiz on the event page
 *   - In-Person Quiz — survey + an admin records the score from the Dashboard
 *
 * Dev setup these tests assume:
 *   - moderator-smoke@test.com / TestUser@2026! has the Moderator role
 *     (seeds and cleans up fixtures — Global Admin has no create perms on
 *     LMS Question / LMS Quiz / LMS Event)
 *   - global-admin@test.com / TestUser@2026! is a Global Admin (the real
 *     PPT admin role; exercises the Dashboard score-recording UI)
 *   - pro@test.com / TestUser@2026! is a plain learner
 *   - The shared "Course Survey" quiz (is_survey=1) exists
 *
 * Everything else (quiz, question, events, registrations, submissions,
 * certificates) is created through the API at the start and deleted at the
 * end, so the suite is safe to rerun.
 */

const PASSWORD = 'TestUser@2026!'
const SEED_EMAIL = 'moderator-smoke@test.com'
const ADMIN_EMAIL = 'global-admin@test.com'
const STUDENT_EMAIL = 'pro@test.com'
const STAMP = Date.now().toString(36)
const TITLE_PREFIX = `E2E Credit Verify ${STAMP}`

test.describe.configure({ mode: 'serial' })
test.setTimeout(120000)

type SurveyAnswer = { question_name: string; answer: string[]; type: string }
type Ctx = {
	surveyQuiz: string
	surveyAnswers: SurveyAnswer[]
	question: string
	creditQuiz: string
	inPersonEvent: string
	onlineEvent: string
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

async function tryDelete(page: Page, doctype: string, name: string) {
	await api(page, 'frappe.client.delete', { doctype, name }).catch(() => {})
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

function yesterday() {
	const d = new Date()
	d.setDate(d.getDate() - 1)
	return d.toISOString().slice(0, 10)
}

async function makeEvent(page: Page, suffix: string, extra: Record<string, unknown>) {
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
		description: 'E2E credit verification event',
		event_details: '<p>E2E credit verification event</p>',
		instructors: [{ instructor: SEED_EMAIL }],
		certification: 1,
		credit_hours: 1,
		survey_quiz: ctx.surveyQuiz,
		published: 1,
		...extra,
	})
	await insert(page, {
		doctype: 'LMS Event Registration',
		event: doc.name,
		member: STUDENT_EMAIL,
	})
	return doc.name as string
}

/** Learners can't read LMS Question, so the admin precomputes the answers. */
async function buildSurveyAnswers(adminPage: Page): Promise<SurveyAnswer[]> {
	const quiz = await api(adminPage, 'frappe.client.get', {
		doctype: 'LMS Quiz',
		name: ctx.surveyQuiz,
	})
	const results: SurveyAnswer[] = []
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

/** Submit the feedback survey through the same endpoint the Vue Quiz uses. */
async function submitSurveyViaApi(page: Page, event: string) {
	return api(page, 'lms.lms.api.submit_event_survey', {
		event,
		results: JSON.stringify(ctx.surveyAnswers),
	})
}

test.describe('Event CEU credit verification', () => {
	test.beforeAll(async ({ browser }) => {
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)

		const surveys = await listNames(page, 'LMS Quiz', { is_survey: 1, title: 'Course Survey' })
		if (!surveys.length) throw new Error('Shared "Course Survey" quiz not found on dev')
		ctx.surveyQuiz = surveys[0]
		ctx.surveyAnswers = await buildSurveyAnswers(page)

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

		ctx.inPersonEvent = await makeEvent(page, 'In-Person', {
			credit_verification: 'In-Person Quiz',
			credit_passing_percentage: 80,
		})
		ctx.onlineEvent = await makeEvent(page, 'Online', {
			credit_verification: 'Online Quiz',
			credit_quiz: quiz.name,
		})
		await page.close()
	})

	test.afterAll(async ({ browser }) => {
		const page = await browser.newPage()
		await login(page, SEED_EMAIL)
		const events = [ctx.inPersonEvent, ctx.onlineEvent].filter(Boolean) as string[]
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
	})

	test('in-person: survey alone does not certify; admin-recorded score does', async ({
		page,
		browser,
	}) => {
		await login(page, STUDENT_EMAIL)
		await page.goto(`/lms/events/${ctx.inPersonEvent}#dashboard`)

		const progress = page.getByTestId('credit-progress')
		await expect(progress).toBeVisible({ timeout: 15000 })
		await expect(progress).toContainText('Scored in person by your instructor')
		await expect(progress.getByText('Pending').last()).toBeVisible()

		const res = await submitSurveyViaApi(page, ctx.inPersonEvent!)
		expect(res.certificate).toBeNull()

		await page.reload()
		await expect(progress).toContainText('Submitted')

		// Admin half in its own context: a GET logout leaves the SPA session
		// cached, so /login would just bounce back to the student's home.
		const adminContext = await browser.newContext()
		const admin = await adminContext.newPage()
		await login(admin, ADMIN_EMAIL)
		await admin.goto(`/lms/events/${ctx.inPersonEvent}#dashboard`)
		const recordBtn = admin
			.getByRole('button', { name: /Record quiz score for/i })
			.first()
		await recordBtn.waitFor({ timeout: 15000 })
		await recordBtn.click()

		const dialog = admin.getByRole('dialog')
		await expect(dialog).toBeVisible()
		const score = dialog.locator('input[type="number"]')
		await score.fill('85')
		await dialog.getByRole('button', { name: 'Save score' }).click()

		await expect(admin.getByText(/passed — certificate issued/i)).toBeVisible({
			timeout: 15000,
		})
		await expect(admin.getByText('Issued').first()).toBeVisible()
		await expect(admin.getByText(/Passed \(admin\) 85%/)).toBeVisible()

		// Student sees it too.
		await page.reload()
		await expect(progress).toContainText('Issued', { timeout: 15000 })
		const certs = await listNames(page, 'LMS Certificate', {
			event_name: ctx.inPersonEvent,
			member: STUDENT_EMAIL,
		})
		expect(certs.length).toBe(1)

		await adminContext.close()
		await logout(page)
	})

	test('online: attendee passes the quiz on the event page and the certificate issues', async ({
		page,
	}) => {
		await login(page, STUDENT_EMAIL)
		const res = await submitSurveyViaApi(page, ctx.onlineEvent!)
		expect(res.certificate).toBeNull()

		await page.goto(`/lms/events/${ctx.onlineEvent}#dashboard`)
		const progress = page.getByTestId('credit-progress')
		await expect(progress).toBeVisible({ timeout: 15000 })
		await expect(progress).toContainText('Open now')

		await page.getByRole('button', { name: 'Take Quiz' }).click()
		await page.getByRole('button', { name: /^Start/ }).click()
		// Single Choices question: option 1 ("Yes") is the correct answer.
		await page.locator('input[type="radio"]').first().check()
		await page.getByRole('button', { name: /^Submit$/ }).click()
		const confirm = page.getByRole('dialog')
		if (await confirm.isVisible().catch(() => false)) {
			await confirm.getByRole('button', { name: /^Submit$/ }).click()
		}

		await expect(
			page.getByText(/You passed! Your certificate has been issued/i)
		).toBeVisible({ timeout: 20000 })

		const certs = await listNames(page, 'LMS Certificate', {
			event_name: ctx.onlineEvent,
			member: STUDENT_EMAIL,
		})
		expect(certs.length).toBe(1)
		await logout(page)
	})
})
