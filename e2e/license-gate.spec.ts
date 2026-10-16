import { test, expect, Page } from '@playwright/test'

/**
 * License gate (CEU broker requirement).
 *
 * Every CEU-bearing entry point needs license type, state and number:
 *   - public signup on an event landing (/e/<slug>) asks for it and the
 *     server rejects the request without it
 *   - a logged-in member without a license sees a banner on every /lms page
 *     and can fix it inline
 *   - Register Now on an event page opens the license dialog instead of
 *     Stripe until the fields are saved
 *
 * TEST DATA assumed on devlms (same as signup-flow.spec.ts):
 *   - PAID_EVENT_SLUG must be a published, paid, future LMS Event
 */

const PAID_EVENT_SLUG = 'upsell-smoke-event'

function uniqueEmail(): string {
	const stamp = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
	return `license-gate+${stamp}@example.com`
}

const PASSWORD = 'TestUser@2026!'

// Bare /lms/signup is deliberately not gated (lead-gen path), which makes it
// the quickest way to mint a logged-in user with no license.
async function signupWithoutLicense(page: Page, email: string) {
	await page.goto('/lms/signup')
	await page.getByLabel('Full name').fill('License Gate')
	await page.getByLabel('Email').fill(email)
	await page.getByLabel('Password').fill(PASSWORD)
	await page.getByRole('button', { name: 'Create account' }).click()
	await page.waitForURL('**/lms', { timeout: 15000 })
}

test.describe('License gate', () => {
	test('event landing modal asks for a license and rejects signup without one', async ({ page }) => {
		const email = uniqueEmail()
		await page.goto(`/e/${PAID_EVENT_SLUG}`)
		await page.locator('[data-action="open-register"]').first().click()

		const signup = page.locator('#register-modal-signup')
		await expect(signup.getByTestId('register-license-fields')).toBeVisible()

		await signup.locator('input[name="full_name"]').fill('No License')
		await signup.locator('input[name="email"]').fill(email)
		await signup.locator('input[name="password"]').fill(PASSWORD)
		await signup.locator('button[type="submit"]').click()

		await expect(page.locator('#register-modal-alert')).toContainText(/license/i, { timeout: 15000 })
		expect(page.url()).toContain(`/e/${PAID_EVENT_SLUG}`)

		// Now with the fields: lands on the in-app event page.
		await signup.locator('select[name="license_type"]').selectOption('OT')
		await signup.locator('input[name="license_state"]').fill('fl')
		await signup.locator('input[name="professional_license_number"]').fill('OT-E2E-0001')
		await Promise.all([
			page.waitForURL(`**/lms/events/${PAID_EVENT_SLUG}**`, { timeout: 25000 }),
			signup.locator('button[type="submit"]').click(),
		])

		// Profile carries the license, so no banner for this user.
		await page.goto('/lms')
		await expect(page.getByTestId('license-banner')).toHaveCount(0)
	})

	test('member without a license sees the banner and can fix it inline', async ({ page }) => {
		await signupWithoutLicense(page, uniqueEmail())

		const banner = page.getByTestId('license-banner')
		await expect(banner).toBeVisible({ timeout: 15000 })
		await expect(banner).toContainText('professional license is missing')

		await banner.getByRole('button', { name: 'Add license' }).click()
		const fields = banner.getByTestId('license-fields')
		await fields.locator('select').selectOption('SLP')
		await fields.getByLabel('State').fill('wa')
		await fields.getByLabel('License number').fill('SLP-E2E-0001')
		await banner.getByRole('button', { name: 'Save license' }).click()

		await expect(banner).toHaveCount(0, { timeout: 15000 })

		// Survives a reload: the flag comes from get_user_info, not local state.
		await page.reload()
		await expect(page.getByTestId('license-banner')).toHaveCount(0)
	})

	test('Register Now on an event opens the license dialog, not Stripe, until saved', async ({ page }) => {
		await signupWithoutLicense(page, uniqueEmail())

		await page.goto(`/lms/events/${PAID_EVENT_SLUG}`)
		const register = page.getByRole('button', { name: 'Register Now' }).filter({ visible: true }).first()
		await expect(register).toBeVisible({ timeout: 20000 })
		await register.click()

		const dialog = page.getByRole('dialog')
		await expect(dialog.getByText('Add your professional license')).toBeVisible()
		expect(page.url()).not.toContain('checkout.stripe.com')

		const fields = dialog.getByTestId('license-fields')
		await fields.locator('select').selectOption('PT')
		await fields.getByLabel('State').fill('FL')
		await fields.getByLabel('License number').fill('PT-E2E-0002')

		// Saving resumes the original action: checkout starts.
		await Promise.all([
			page.waitForURL(/checkout\.stripe\.com/, { timeout: 30000 }),
			dialog.getByRole('button', { name: 'Save and continue' }).click(),
		])
		expect(page.url()).toContain('checkout.stripe.com')
	})
})
