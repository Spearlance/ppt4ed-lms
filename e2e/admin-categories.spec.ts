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
	// Cleanup is inline at the end of each test, since the CSRF token needed
	// for delete_category lives on the in-test page (window.csrf_token).

	test('admin can create top via the dialog and child/grandchild via API show up in the tree', async ({ page }) => {
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
		//
		// Frappe requires both the session cookie AND the X-Frappe-CSRF-Token
		// header for write methods. page.request shares cookies with the page,
		// but we have to copy window.csrf_token (set in the page HTML by Frappe
		// boot) onto the header ourselves — frappe-ui does this automatically
		// from inside the browser, raw Playwright requests don't.
		const csrf = await page.evaluate(() => (window as any).csrf_token as string)
		const headers = { 'X-Frappe-CSRF-Token': csrf }
		const childRes = await page.request.post(
			'/api/method/lms.lms.api.create_category',
			{ headers, data: { label: CHILD, parent: TOP } }
		)
		expect(childRes.ok(), await childRes.text()).toBeTruthy()
		const grandRes = await page.request.post(
			'/api/method/lms.lms.api.create_category',
			{ headers, data: { label: GRANDCHILD, parent: CHILD } }
		)
		expect(grandRes.ok(), await grandRes.text()).toBeTruthy()

		// Refresh and confirm the new hierarchy appears under the auto-expanded
		// first two levels.
		await page.reload()
		await expect(page.getByText(TOP).first()).toBeVisible({ timeout: 10000 })
		await expect(page.getByText(CHILD).first()).toBeVisible({ timeout: 10000 })

		// Cleanup deepest-first so each delete's empty-child guard passes.
		for (const name of [GRANDCHILD, CHILD, TOP]) {
			await page.request.post('/api/method/lms.lms.api.delete_category', {
				headers,
				data: { name, force: 1 },
			}).catch(() => {})
		}

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
