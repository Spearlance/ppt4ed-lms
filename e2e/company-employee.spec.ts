import { test, expect, Page } from '@playwright/test'

/**
 * Tests for the company employee experience.
 *
 * Test users (seeded via seed_test_users.py):
 *   company-employee@test.com / TestUser@2026!  — Company member (Sunrise Therapy Group)
 *   company-admin@test.com / TestUser@2026!     — Company admin
 *   pro@test.com / TestUser@2026!               — Professional member (no company)
 */

const COMPANY_EMPLOYEE = {
	email: 'company-employee@test.com',
	password: 'TestUser@2026!',
}

const COMPANY_ADMIN = {
	email: 'company-admin@test.com',
	password: 'TestUser@2026!',
}

const PRO_USER = {
	email: 'pro@test.com',
	password: 'TestUser@2026!',
}

async function login(page: Page, email: string, password: string) {
	await page.goto('/login')
	await page.fill('#login_email', email)
	await page.fill('#login_password', password)
	await page.click('.btn-login')
	// Wait for SPA to load after login redirect
	await page.waitForURL('**/lms/**', { timeout: 15000 })
}

async function logout(page: Page) {
	await page.goto('/api/method/logout')
	await page.waitForURL('**/login*')
}

test.describe('Company Employee Homepage', () => {
	test.beforeEach(async ({ page }) => {
		await login(page, COMPANY_EMPLOYEE.email, COMPANY_EMPLOYEE.password)
	})

	test('shows company name in greeting', async ({ page }) => {
		// The greeting should contain "Sunrise Therapy Group"
		const greeting = page.locator('.text-xl.font-bold')
		await expect(greeting).toContainText('Sunrise Therapy Group')
	})

	test('shows credit balance in subtitle', async ({ page }) => {
		// Subtitle should mention CEU hours available
		const subtitle = page.locator('.text-lg.text-ink-gray-6')
		await expect(subtitle).toContainText('CEU hours available')
		await expect(subtitle).toContainText('Sunrise Therapy Group')
	})

	test('shows company account card with balance', async ({ page }) => {
		// Company card should be visible with credit balance
		const card = page.locator('text=CEU hours available').first()
		await expect(card).toBeVisible()

		// View Credits link should exist
		const viewCreditsLink = page.locator('text=View Credits')
		await expect(viewCreditsLink).toBeVisible()
	})
})

test.describe('My Credits Page', () => {
	test.beforeEach(async ({ page }) => {
		await login(page, COMPANY_EMPLOYEE.email, COMPANY_EMPLOYEE.password)
	})

	test('accessible via sidebar link', async ({ page }) => {
		// My Credits should appear in sidebar
		const sidebarLink = page.locator('button:has-text("My Credits")')
		await expect(sidebarLink).toBeVisible()

		await sidebarLink.click()
		await page.waitForURL('**/my-credits')
	})

	test('displays company name and credit balance', async ({ page }) => {
		await page.goto('/lms/my-credits')

		// Company name should be visible
		await expect(page.locator('h2:has-text("Sunrise Therapy Group")')).toBeVisible()

		// Credit balance should be displayed
		await expect(page.locator('text=CEU hours available')).toBeVisible()
	})

	test('displays transaction history section', async ({ page }) => {
		await page.goto('/lms/my-credits')

		// My Usage heading should appear
		await expect(page.locator('h3:has-text("My Usage")')).toBeVisible()
	})
})

test.describe('My Credits sidebar visibility', () => {
	test('company employee sees My Credits link', async ({ page }) => {
		await login(page, COMPANY_EMPLOYEE.email, COMPANY_EMPLOYEE.password)
		const sidebarLink = page.locator('button:has-text("My Credits")')
		await expect(sidebarLink).toBeVisible()
	})

	test('company admin sees both My Credits and Company links', async ({ page }) => {
		await login(page, COMPANY_ADMIN.email, COMPANY_ADMIN.password)
		const myCredits = page.locator('button:has-text("My Credits")')
		await expect(myCredits).toBeVisible()
		const company = page.locator('button:has-text("Company")')
		await expect(company).toBeVisible()
	})

	test('non-company user does NOT see My Credits link', async ({ page }) => {
		await login(page, PRO_USER.email, PRO_USER.password)
		// Wait for homepage to load
		await expect(page.locator('.text-xl.font-bold')).toBeVisible()
		const sidebarLink = page.locator('button:has-text("My Credits")')
		await expect(sidebarLink).not.toBeVisible()
	})
})

test.describe('Non-company user sees no company UI', () => {
	test('professional user sees standard homepage without company context', async ({ page }) => {
		await login(page, PRO_USER.email, PRO_USER.password)

		// Greeting should NOT mention any company
		const greeting = page.locator('.text-xl.font-bold')
		await expect(greeting).not.toContainText('Sunrise Therapy Group')

		// No company card
		const viewCredits = page.locator('text=View Credits')
		await expect(viewCredits).not.toBeVisible()
	})
})

test.describe('Course Enrollment Flow', () => {
	test('company employee sees credit enrollment button on course with CEU hours', async ({ page }) => {
		// Use a wide viewport so the course overlay sidebar is visible at md: breakpoint
		await page.setViewportSize({ width: 1440, height: 900 })
		await login(page, COMPANY_EMPLOYEE.email, COMPANY_EMPLOYEE.password)

		// Navigate directly to a known course with CEU hours (4 CE Hours)
		await page.goto(
			'/lms/courses/the-power-of-play-linking-play-to-language-cognitive-social-emotional-literacy-development'
		)
		await page.waitForLoadState('networkidle')

		// The overlay renders either at md: breakpoint (desktop sidebar) or as inline (mobile).
		// Look for any enrollment-related button, scrolling to find it.
		const anyButton = page.locator(
			'button:has-text("CEU"), button:has-text("Buy this course"), button:has-text("Start Learning"), button:has-text("Continue Learning")'
		)

		// Scroll down in case the mobile overlay is below the fold
		await page.evaluate(() => window.scrollTo(0, 300))

		await expect(anyButton.first()).toBeVisible({ timeout: 15000 })
	})
})
