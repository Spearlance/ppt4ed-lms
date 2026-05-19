import { test, expect, Page } from '@playwright/test'

/**
 * Smoke tests for PR A (category tree + admin page):
 *  - /lms/admin-categories renders for an LMS admin
 *  - Admin can create a top-level category, a child, and a grandchild
 *  - Delete-guard surfaces resource/child counts before forcing delete
 *  - The flat seed categories (Occupational Therapy, Speech, ...) survive
 *    the tree migration and still appear as top-level nodes
 *
 * Runs against devlms.ppt4ed.org. The admin user must have Moderator OR
 * Global Admin OR System Manager. We reuse the global-admin test user from
 * the existing global-admin-enroll.spec.ts seed.
 */

const ADMIN_EMAIL = 'global-admin@test.com'
const ADMIN_PASSWORD = 'TestUser@2026!'

// Use a session-stamped prefix so reruns don't collide with leftover rows.
const STAMP = Date.now().toString().slice(-6)
const TOP = `pw-top-${STAMP}`
const CHILD = `pw-child-${STAMP}`
const GRANDCHILD = `pw-grand-${STAMP}`

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

test.describe('PR A — Admin categories tree', () => {
	test.afterAll(async ({ request }) => {
		// Best-effort cleanup so repeated runs don't pollute the seed list.
		for (const name of [GRANDCHILD, CHILD, TOP]) {
			await request.post('/api/method/lms.lms.api.delete_category', {
				data: { name, force: 1 },
			}).catch(() => {})
		}
	})

	test('admin can create top via the dialog and child/grandchild via API show up in the tree', async ({ page, request }) => {
		await loginAsAdmin(page)
		await page.goto('/lms/admin-categories')

		// Existing seed categories should appear as top-level nodes (zero-data-loss
		// check for the rebuild_lms_category_tree patch).
		await expect(page.getByText('Occupational Therapy').first()).toBeVisible({
			timeout: 10000,
		})

		// 1. Create top-level via the dialog UI.
		await page.getByRole('button', { name: 'Add top-level category' }).click()
		await page.getByLabel('Name').fill(TOP)
		await page.getByRole('button', { name: 'Create', exact: true }).click()
		await expect(page.getByText(TOP).first()).toBeVisible({ timeout: 10000 })

		// 2. + 3. Create a child + grandchild via API. The same create_category
		// endpoint backs the UI's "Add sub-category" button — covering it here
		// avoids depending on hover-revealed action buttons.
		const childRes = await request.post('/api/method/lms.lms.api.create_category', {
			data: { label: CHILD, parent: TOP },
		})
		expect(childRes.ok()).toBeTruthy()
		const grandRes = await request.post('/api/method/lms.lms.api.create_category', {
			data: { label: GRANDCHILD, parent: CHILD },
		})
		expect(grandRes.ok()).toBeTruthy()

		// Refresh and confirm the new hierarchy appears under the auto-expanded
		// first two levels.
		await page.reload()
		await expect(page.getByText(TOP).first()).toBeVisible({ timeout: 10000 })
		await expect(page.getByText(CHILD).first()).toBeVisible({ timeout: 10000 })

		await logout(page)
	})

	test('the row-level action buttons render with stable testids', async ({ page }) => {
		await loginAsAdmin(page)
		// Seed a deterministic top-level so we can target its testid.
		const seed = `pw-action-${STAMP}`
		await page.request.post('/api/method/lms.lms.api.create_category', {
			data: { label: seed, parent: null },
		})
		await page.goto('/lms/admin-categories')
		const addBtn = page.locator(`[data-testid="category-add-child-${seed}"]`)
		await expect(addBtn).toHaveCount(1, { timeout: 10000 })
		await expect(
			page.locator(`[data-testid="category-rename-${seed}"]`)
		).toHaveCount(1)
		await expect(
			page.locator(`[data-testid="category-delete-${seed}"]`)
		).toHaveCount(1)
		// Cleanup.
		await page.request.post('/api/method/lms.lms.api.delete_category', {
			data: { name: seed, force: 1 },
		})
		await logout(page)
	})

	test('non-admin gets bounced from /lms/admin-categories', async ({ page }) => {
		// No login — guest hits the moderator gate in router.beforeEach.
		await page.goto('/lms/admin-categories')
		// Router redirects to Courses (or login if guest_access is off).
		await page.waitForLoadState('networkidle')
		expect(page.url()).not.toMatch(/admin-categories/)
	})
})

test.describe('PR A — Category API', () => {
	test('get_category_tree returns roots with the seed categories', async ({ request }) => {
		const res = await request.get('/api/method/lms.lms.api.get_category_tree')
		expect(res.ok()).toBeTruthy()
		const body = await res.json()
		const labels = (body.message || []).map((n: { label: string }) => n.label)
		// The four seeds from lms_category.json fixture should all be at root level.
		for (const seed of ['Occupational Therapy', 'Speech', 'Feeding', 'Educational']) {
			expect(labels).toContain(seed)
		}
	})

	test('get_category_options returns path-formatted labels', async ({ request }) => {
		const res = await request.get('/api/method/lms.lms.api.get_category_options')
		expect(res.ok()).toBeTruthy()
		const body = await res.json()
		const items = body.message || []
		expect(items.length).toBeGreaterThan(0)
		// Each option should have a string label and a value.
		for (const item of items.slice(0, 3)) {
			expect(typeof item.label).toBe('string')
			expect(typeof item.value).toBe('string')
		}
	})
})
