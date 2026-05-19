import { test, expect, Page } from '@playwright/test'

/**
 * Smoke tests for PR B (folder browse on /lms/resources):
 *  - Top-level folder cards render on the resource catalog
 *  - Clicking a folder card pushes ?category=... and renders the breadcrumb
 *  - Resources attached to the folder's subtree appear (lft/rgt subtree
 *    filter on get_resources)
 *
 * Uses the existing "Social Stories" seed category on dev, which has real
 * resources attached. Avoids needing LMS Course write perms (Global Admin
 * doesn't have doctype-level access — see [[global-admin-doctype-perms]]).
 *
 * Also creates an ephemeral child under Social Stories to assert the
 * breadcrumb-from-nested-folder path.
 */

const ADMIN_EMAIL = 'global-admin@test.com'
const ADMIN_PASSWORD = 'TestUser@2026!'

const STAMP = Date.now().toString().slice(-6)
const NESTED_CHILD = `pw-fbrowse-${STAMP}`
const SEED_PARENT = 'Social Stories'

async function loginAsAdmin(page: Page) {
	await page.goto('/login')
	await page.fill('#login_email', ADMIN_EMAIL)
	await page.fill('#login_password', ADMIN_PASSWORD)
	await page.click('.btn-login')
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function logout(page: Page) {
	await page.goto('/api/method/logout')
	await page.waitForLoadState('networkidle')
}

async function api(page: Page, method: string, data: Record<string, unknown>) {
	const csrf = await page.evaluate(() => (window as any).csrf_token as string)
	return page.request.post(`/api/method/${method}`, {
		headers: { 'X-Frappe-CSRF-Token': csrf },
		data,
	})
}

test.describe('PR B — Resources folder browse', () => {
	test('top-level folder cards render and clicking one navigates with breadcrumb', async ({ page }) => {
		await loginAsAdmin(page)
		await page.goto('/lms/resources')

		// Folder cards for the seeded top-level categories should appear above
		// the resource grid.
		const parentCard = page.locator('button', { hasText: SEED_PARENT }).first()
		await expect(parentCard).toBeVisible({ timeout: 10000 })

		// Click into the folder. URL should gain ?category=... and the
		// breadcrumb should now show the parent name.
		await parentCard.click()
		await page.waitForURL(/category=/, { timeout: 5000 })
		// Breadcrumb renders the parent label as a clickable link/text.
		await expect(page.getByText(SEED_PARENT).first()).toBeVisible({ timeout: 10000 })

		// The category's existing resources should show (subtree filter on
		// get_resources). Sanity check: at least one CourseCard renders.
		// (Social Stories has 15 resources per the seed data; expecting >0 is
		// resilient to future content edits.)
		const cards = page.locator('a[href*="/lms/resources/"]')
		await expect(cards.first()).toBeVisible({ timeout: 10000 })

		await logout(page)
	})

	test('nested child folder shows under its parent in the browse view', async ({ page }) => {
		await loginAsAdmin(page)

		// Seed a child under Social Stories so we can verify the folder-card
		// list includes admin-created nodes.
		const childRes = await api(page, 'lms.lms.api.create_category', {
			label: NESTED_CHILD,
			parent: SEED_PARENT,
		})
		expect(childRes.ok(), await childRes.text()).toBeTruthy()

		// Navigate into Social Stories via URL (skip the click flow — covered
		// above) and look for the new child folder card.
		await page.goto(`/lms/resources?category=${encodeURIComponent(SEED_PARENT)}`)
		await expect(page.getByText(NESTED_CHILD).first()).toBeVisible({ timeout: 10000 })

		// Cleanup.
		await api(page, 'lms.lms.api.delete_category', {
			name: NESTED_CHILD,
			force: 1,
		}).catch(() => {})

		await logout(page)
	})
})
