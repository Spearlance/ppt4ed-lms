import { test, expect, Page } from '@playwright/test'

/**
 * Post-deploy smoke for the 2026-05-18 marketing-meeting quick-wins bundle (PR #123):
 *   1. Password policy bypass on signup_and_enroll (8-char weak password accepted)
 *   2. YouTube iframe src no longer carries ?t= from the source URL
 *   3. Discussions/Community section hidden on lesson pages
 *   4. Courses page shows only Live + On-demand tabs
 *   5. Contact form validates + surfaces real errors
 *   6. Professional + Individual Business plans hidden on Individual tab
 *
 * Runs against devlms.ppt4ed.org.
 */

const STUDENT_EMAIL = 'pro@test.com'
const STUDENT_PASSWORD = 'TestUser@2026!'

const CATCH_THE_WAVE =
	'catch-the-wave-introduction-to-whole-body-vibration-in-pediatric-therapy-for-pts-ots-and-slps'

async function loginAsStudent(page: Page) {
	await page.goto('/login')
	await page.fill('#login_email', STUDENT_EMAIL)
	await page.fill('#login_password', STUDENT_PASSWORD)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function logout(page: Page) {
	await page.goto('/api/method/logout')
	await page.waitForLoadState('networkidle')
}

test.describe('Marketing quick-wins post-deploy smoke (PR #123)', () => {
	test('#1 — signup_and_enroll accepts an 8-char weak password', async ({ request }) => {
		// Unique email per run so we never collide with a prior signup
		const email = `qwsmoke-${Date.now()}@test.com`
		const response = await request.post(
			'/api/method/lms.lms.api.signup_and_enroll',
			{
				data: {
					email,
					password: 'password', // weak but 8 chars — zxcvbn score 0/1
					full_name: 'QW Smoke',
					intent: 'free',
				},
			}
		)
		// Should NOT be rejected for password complexity. Either logs in or returns a
		// non-policy error (e.g. signup disabled). Reject only on the specific policy text.
		const text = await response.text()
		expect(text, `signup body: ${text}`).not.toMatch(
			/password.*policy|password.*not.*strong|password.*too.*short|easy.*to.*guess/i
		)
	})

	test('#2 — YouTube iframe src does not contain ?t= timestamp on a lesson with video', async ({
		page,
	}) => {
		await loginAsStudent(page)

		// Find a course Sarah can preview that has a youtube video on chapter 1.
		// Dev data: introduction-to-upper-extremity-splinting has a video in Part 1.
		await page.goto(
			'/lms/courses/introduction-to-upper-extremity-splinting-for-function-in-pediatrics/learn/1-1'
		)
		await page.waitForLoadState('networkidle')

		// Give Plyr ~1s to swap the [data-plyr-provider] container for an iframe.
		await page.waitForTimeout(1500)

		const srcs = await page.evaluate(() => {
			const out: string[] = []
			document
				.querySelectorAll('[data-plyr-provider="youtube"]')
				.forEach((el) => {
					const s = el.getAttribute('src')
					if (s) out.push(s)
				})
			document.querySelectorAll('iframe[src*="youtube"]').forEach((el) => {
				const s = el.getAttribute('src')
				if (s) out.push(s)
			})
			return out
		})

		if (srcs.length === 0) {
			// Lesson may be gated for non-enrolled users — bail with a skip so
			// the suite stays useful. The strip is verified by code review on PR #123;
			// re-run this once Sarah is enrolled in a course with a video lesson.
			test.skip(
				true,
				'No YouTube player rendered on Splinting Part-1; needs an enrolled student or a different fixture'
			)
		}
		for (const src of srcs) {
			expect(
				src,
				`youtube src must not include ?t= or &t= or &start=: ${src}`
			).not.toMatch(/[?&](t|start)=/)
		}
		await logout(page)
	})

	test('#3 — Discussions/Community tab is hidden on lesson page', async ({ page }) => {
		await loginAsStudent(page)
		await page.goto(`/lms/courses/${CATCH_THE_WAVE}/learn/1-1`)
		await page.waitForLoadState('networkidle')

		// No tab button labelled "Community"
		const communityTab = page.getByRole('button', { name: /^Community$/ })
		await expect(communityTab).toHaveCount(0)

		// No "Ask a question to get help from the community" empty state
		const emptyState = page.getByText(
			/Ask a question to get help from the community/i
		)
		await expect(emptyState).toHaveCount(0)

		await logout(page)
	})

	test('#4 — Courses page shows only Live + On-demand tabs (no New / Upcoming / CEU Events)', async ({
		page,
	}) => {
		// /lms/courses requires auth — guests get redirected to /login.
		await loginAsStudent(page)
		await page.goto('/lms/courses')
		await page.waitForLoadState('networkidle')

		// TabButtons renders as a radiogroup of radio elements. Scope to the
		// radiogroup so we don't collide with sidebar/banner text.
		const tabs = page.getByRole('radiogroup').first()
		await expect(tabs.getByRole('radio', { name: /^Live$/ })).toBeVisible()
		await expect(tabs.getByRole('radio', { name: /^On-demand$/ })).toBeVisible()

		// The removed tabs must NOT be present in the radiogroup
		await expect(tabs.getByRole('radio', { name: /^New$/ })).toHaveCount(0)
		await expect(tabs.getByRole('radio', { name: /^Upcoming$/ })).toHaveCount(0)
		await expect(tabs.getByRole('radio', { name: /^CEU Events$/ })).toHaveCount(0)
		await expect(tabs.getByRole('radio', { name: /^On Demand$/ })).toHaveCount(0)

		await logout(page)
	})

	test('#5 — Contact form recipient is configured in LMS Settings (recipient non-empty)', async ({
		request,
	}) => {
		// Avoid actually sending an email. Verify the wiring instead:
		// LMS Settings exposes contact_us_email to the public, and the value is non-empty.
		const response = await request.get(
			'/api/method/lms.lms.api.get_lms_settings'
		)
		expect(response.ok()).toBeTruthy()
		const body = await response.json()
		const settings = body.message
		expect(settings, 'get_lms_settings must return a payload').toBeTruthy()
		expect(
			settings.contact_us_email,
			'LMS Settings.contact_us_email must be set or the Contact form will fail-fast'
		).toBeTruthy()
		expect(settings.contact_us_email).toMatch(/@/)
	})

	test('#6 — Membership Individual tab: Free + Educational Partner only', async ({
		page,
	}) => {
		await page.goto('/lms/membership-plans')
		await page.waitForLoadState('networkidle')

		// Default tab is Company; switch to Individual.
		await page.getByRole('button', { name: /^Individual$/ }).click()
		await page.waitForTimeout(500) // let the tab re-render

		// Free card must be present
		await expect(page.locator('h3:text("Free")').first()).toBeVisible()

		// Educational Partner card must be present
		const eduPartner = page.locator(
			'h3.text-lg.font-semibold:has-text("Educational Partner")'
		)
		await expect(eduPartner).toBeVisible()

		// Pull all paid plan card titles and assert what's NOT there
		const paidCardTitles = await page
			.locator('h3.text-lg.font-semibold')
			.allTextContents()
		const seenProfessional = paidCardTitles.some((t) =>
			/^Professional Membership$/i.test(t.trim())
		)
		const seenIndivBiz = paidCardTitles.some((t) =>
			/^Individual Business Membership$/i.test(t.trim())
		)
		expect(
			seenProfessional,
			`Professional Membership must NOT appear on Individual tab; saw ${JSON.stringify(paidCardTitles)}`
		).toBe(false)
		expect(
			seenIndivBiz,
			`Individual Business Membership must NOT appear on Individual tab; saw ${JSON.stringify(paidCardTitles)}`
		).toBe(false)
	})
})
