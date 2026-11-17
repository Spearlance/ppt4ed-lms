import { test, expect, Page } from '@playwright/test'

/**
 * Admins edit other people's profiles on devlms.
 *
 * A Moderator opens a learner's profile, uses Edit Profile and the change is
 * saved to the learner's account. A learner never gets the button on someone
 * else's profile, and the API refuses them too.
 *
 * Dev setup: moderator-smoke@test.com (Moderator) and pro@test.com (learner),
 * both with password TestUser@2026!
 */

const PASSWORD = 'TestUser@2026!'
const ADMIN_EMAIL = 'moderator-smoke@test.com'
const STUDENT_EMAIL = 'pro@test.com'
const STAMP = Date.now().toString(36)
const HEADLINE = `E2E headline ${STAMP}`
const UPDATE = '/api/method/lms.lms.profile.update_profile'

test.describe.configure({ mode: 'serial' })
test.setTimeout(120000)

const ctx: { studentUsername?: string; adminUsername?: string; original?: string } = {}

async function login(page: Page, email: string) {
	await page.goto('/login')
	await page.fill('#login_email', email)
	await page.fill('#login_password', PASSWORD)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function post(page: Page, url: string, data: Record<string, unknown>) {
	const csrf = await page.evaluate(() => (window as any).csrf_token as string)
	return page.request.post(url, { headers: { 'X-Frappe-CSRF-Token': csrf }, data })
}

async function ownInfo(page: Page) {
	const res = await page.request.get('/api/method/lms.lms.api.get_user_info')
	expect(res.ok(), await res.text()).toBeTruthy()
	return (await res.json()).message
}

async function headlineOf(page: Page, username: string) {
	const res = await page.request.get(
		`/api/method/lms.lms.api.get_profile_details?username=${username}`
	)
	expect(res.ok(), await res.text()).toBeTruthy()
	return ((await res.json()).message.headline || '') as string
}

test.describe('Admin edits another profile', () => {
	test.beforeAll(async ({ browser }) => {
		const student = await browser.newPage()
		await login(student, STUDENT_EMAIL)
		ctx.studentUsername = (await ownInfo(student)).username
		ctx.original = await headlineOf(student, ctx.studentUsername!)
		await student.close()

		const admin = await browser.newPage()
		await login(admin, ADMIN_EMAIL)
		ctx.adminUsername = (await ownInfo(admin)).username
		await admin.close()
	})

	test.afterAll(async ({ browser }) => {
		// Put the learner's headline back the way it was.
		if (ctx.original === undefined) return
		const page = await browser.newPage()
		await login(page, ADMIN_EMAIL)
		const res = await post(page, UPDATE, {
			user: STUDENT_EMAIL,
			fields: { headline: ctx.original },
		})
		if (!res.ok()) console.warn(`admin-edit-profile: could not restore headline: ${await res.text()}`)
		await page.close()
	})

	test('a learner gets no Edit Profile button on someone else and the API refuses', async ({ page }) => {
		await login(page, STUDENT_EMAIL)
		await page.goto(`/lms/user/${ctx.adminUsername}`)
		await expect(page.getByRole('button', { name: 'About', exact: true })).toBeVisible({
			timeout: 15000,
		})
		await expect(page.getByRole('button', { name: 'Edit Profile' })).toHaveCount(0)

		const res = await post(page, UPDATE, {
			user: ADMIN_EMAIL,
			fields: { headline: 'should not save' },
		})
		expect(res.status()).toBe(403)

		// Their own profile still has it.
		await page.goto(`/lms/user/${ctx.studentUsername}`)
		await expect(page.getByRole('button', { name: 'Edit Profile' })).toBeVisible({ timeout: 15000 })
	})

	test('an admin edits a learner profile from the profile page', async ({ page }) => {
		await login(page, ADMIN_EMAIL)
		await page.goto(`/lms/user/${ctx.studentUsername}`)
		await page.getByRole('button', { name: 'Edit Profile' }).click()

		const dialog = page.getByRole('dialog')
		await expect(dialog.getByTestId('editing-other-profile')).toBeVisible()
		// Nothing has been changed yet, so nothing is pending.
		await page.waitForTimeout(1500)
		await expect(dialog.getByText('Not Saved')).toHaveCount(0)
		const headline = dialog.getByLabel('Headline')
		await headline.fill(HEADLINE)
		await expect(dialog.getByText('Not Saved')).toBeVisible()
		await dialog.getByRole('button', { name: 'Save', exact: true }).click()

		await expect(dialog).toBeHidden({ timeout: 15000 })
		await expect(page.getByText(HEADLINE).first()).toBeVisible({ timeout: 15000 })
		expect(await headlineOf(page, ctx.studentUsername!)).toBe(HEADLINE)

		// The admin is still signed in as themselves.
		expect((await ownInfo(page)).email).toBe(ADMIN_EMAIL)
	})

	test('an admin cannot change fields outside the dialog', async ({ page }) => {
		await login(page, ADMIN_EMAIL)
		const res = await post(page, UPDATE, {
			user: STUDENT_EMAIL,
			fields: { enabled: '0' },
		})
		expect(res.ok()).toBeFalsy()
		// The learner can still sign in.
		const fresh = await page.context().browser()!.newPage()
		await login(fresh, STUDENT_EMAIL)
		await fresh.close()
	})
})
