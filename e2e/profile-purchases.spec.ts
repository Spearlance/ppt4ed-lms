import { test, expect, Page } from '@playwright/test'

/**
 * Profile > Purchases tab.
 *
 * A member sees a Purchases tab on their own profile listing every Stripe
 * charge linked to them, each with a "View receipt" link to the Stripe-hosted
 * receipt. The tab is private: it is hidden on other people's profiles and
 * the API refuses to return another member's rows to a non-admin.
 *
 * TEST DATA assumed on devlms:
 *   - OTHER_PROFILE must be an existing username (post-deploy-smoke uses it)
 */

const OTHER_PROFILE = 'sarah'
const PASSWORD = 'TestUser@2026!'

function uniqueEmail(): string {
	const stamp = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
	return `purchases+${stamp}@example.com`
}

async function signup(page: Page, email: string) {
	await page.goto('/lms/signup')
	await page.getByLabel('Full name').fill('Purchases Tab')
	await page.getByLabel('Email').fill(email)
	await page.getByLabel('Password').fill(PASSWORD)
	await page.getByRole('button', { name: 'Create account' }).click()
	await page.waitForURL('**/lms', { timeout: 15000 })
}

async function ownUsername(page: Page): Promise<string> {
	const res = await page.request.get('/api/method/lms.lms.api.get_user_info')
	expect(res.ok(), await res.text()).toBeTruthy()
	const body = await res.json()
	return body.message.username as string
}

test.describe('Profile purchases', () => {
	test('own profile shows the Purchases tab with an empty state for a new member', async ({ page }) => {
		const email = uniqueEmail()
		await signup(page, email)
		const username = await ownUsername(page)

		await page.goto(`/lms/user/${username}`)
		const tab = page.getByRole('button', { name: 'Purchases' })
		await expect(tab).toBeVisible({ timeout: 15000 })
		await tab.click()

		await page.waitForURL(`**/lms/user/${username}/purchases`, { timeout: 10000 })
		const panel = page.getByTestId('profile-purchases')
		await expect(panel).toBeVisible()
		await expect(panel.getByText('No purchases yet.')).toBeVisible({ timeout: 10000 })
	})

	test('the tab is hidden on another member profile and the API refuses their rows', async ({ page }) => {
		const email = uniqueEmail()
		await signup(page, email)

		await page.goto(`/lms/user/${OTHER_PROFILE}`)
		await expect(page.getByRole('button', { name: 'Certificates' })).toBeVisible({ timeout: 15000 })
		await expect(page.getByRole('button', { name: 'Purchases' })).toHaveCount(0)

		const csrf = await page.evaluate(() => (window as any).csrf_token as string)
		const headers = { 'X-Frappe-CSRF-Token': csrf }

		const mine = await page.request.post('/api/method/lms.lms.ceu_transactions.get_member_purchases', {
			headers,
			data: {},
		})
		expect(mine.ok(), await mine.text()).toBeTruthy()
		expect((await mine.json()).message).toEqual([])

		const theirs = await page.request.post('/api/method/lms.lms.ceu_transactions.get_member_purchases', {
			headers,
			data: { member: 'Administrator' },
		})
		expect(theirs.status()).toBe(403)
	})
})
