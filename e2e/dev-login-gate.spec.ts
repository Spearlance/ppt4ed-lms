import { test, expect } from '@playwright/test'

/**
 * Verification for PR #102 — confirm the hostname-allowlist gate
 * renders Test Logins on devlms but defaults to hide elsewhere.
 *
 * Kept as a permanent regression so the next gate tweak fails this
 * test if it accidentally hides the dev affordance.
 */

test.describe('Dev login card gate (PR #102)', () => {
	test('Test Logins card renders on devlms /login', async ({ page }) => {
		await page.goto('https://devlms.ppt4ed.org/login')

		// The card injects a div with id="dev-login-card" after the bundle loads.
		await expect(page.locator('#dev-login-card')).toBeVisible({ timeout: 10000 })
		await expect(page.getByText('Test Logins')).toBeVisible()
		await expect(page.getByText('Sarah Professional')).toBeVisible()
	})
})
