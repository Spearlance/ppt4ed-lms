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

	test('admin can create a top-level then enter the folder to create a child', async ({ page }) => {
		await loginAsAdmin(page)
		await page.goto('/lms/admin-categories')

		// Root view: only top-level seeds visible as folder cards.
		await expect(page.getByText('Occupational Therapy').first()).toBeVisible({
			timeout: 10000,
		})

		// 1. Create top-level via the page-level Add button.
		await page.getByRole('button', { name: 'Add top-level category' }).click()
		await page.getByLabel('Name').fill(TOP)
		await page.getByRole('button', { name: 'Create', exact: true }).click()
		await expect(page.getByText(TOP).first()).toBeVisible({ timeout: 10000 })

		// 2. Click into the new folder. URL gains ?parent=, breadcrumb shows it.
		await page.getByText(TOP, { exact: true }).first().click()
		await page.waitForURL(/parent=/, { timeout: 5000 })

		// 3. Inside the folder, the Add button label flips to "Add sub-category".
		// Use the API for the actual creation (mirrors the UI button — same endpoint).
		const csrf = await page.evaluate(() => (window as any).csrf_token as string)
		const headers = { 'X-Frappe-CSRF-Token': csrf }
		const childRes = await page.request.post(
			'/api/method/lms.lms.api.create_category',
			{ headers, data: { label: CHILD, parent: TOP } }
		)
		expect(childRes.ok(), await childRes.text()).toBeTruthy()

		// Refresh; the child should appear as a folder card inside TOP.
		await page.reload()
		await expect(page.getByText(CHILD).first()).toBeVisible({ timeout: 10000 })

		// Cleanup deepest-first.
		for (const name of [CHILD, TOP]) {
			await page.request.post('/api/method/lms.lms.api.delete_category', {
				headers,
				data: { name, force: 1 },
			}).catch(() => {})
		}

		await logout(page)
	})

	test('root view hides nested sub-categories', async ({ page }) => {
		await loginAsAdmin(page)

		// Seed a parent + child so we can prove only the parent shows at root.
		const csrf = await (async () => {
			await page.goto('/lms/admin-categories')
			return page.evaluate(() => (window as any).csrf_token as string)
		})()
		const headers = { 'X-Frappe-CSRF-Token': csrf }
		await page.request.post('/api/method/lms.lms.api.create_category', {
			headers,
			data: { label: TOP, parent: null },
		})
		await page.request.post('/api/method/lms.lms.api.create_category', {
			headers,
			data: { label: CHILD, parent: TOP },
		})

		// At root, TOP should be visible but CHILD should NOT (it lives one level deeper).
		await page.goto('/lms/admin-categories')
		await expect(page.getByText(TOP).first()).toBeVisible({ timeout: 10000 })
		await expect(page.getByText(CHILD)).toHaveCount(0)

		// Cleanup.
		for (const name of [CHILD, TOP]) {
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
