import { test, expect, Page } from '@playwright/test'
import * as path from 'path'

/**
 * Visual walkthrough — captures full-page screenshots of every surface
 * touched by PRs #65–#70 in both guest and logged-in states. Run once
 * post-deploy and eyeball the screenshots in screenshots-walkthrough/.
 *
 * Not part of the post-deploy smoke (slow + visual).
 */

const FREE_COURSE_SLUG =
	'the-power-of-play-linking-play-to-language-cognitive-social-emotional-literacy-development'
const EVENT_SLUG = 'pediatric-adaptive-equipment-evaluation-and-fitting'
const SHOTS_DIR = path.join(process.cwd(), 'screenshots-walkthrough')

async function shot(page: Page, name: string) {
	await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
	await page.screenshot({ path: path.join(SHOTS_DIR, `${name}.png`), fullPage: true })
}

test.describe.configure({ mode: 'serial' })

test.describe('Visual walkthrough — guest', () => {
	test('01 /lms/signup', async ({ page }) => {
		await page.goto('/lms/signup')
		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
		await shot(page, '01-guest-signup')
	})

	test('02 /lms/membership-plans (Company tab)', async ({ page }) => {
		await page.goto('/lms/membership-plans')
		await expect(page.getByRole('heading', { name: 'Choose Your Plan' })).toBeVisible()
		await shot(page, '02-guest-plans-company')
	})

	test('03 /lms/membership-plans (Individual tab — Free + paid cards)', async ({ page }) => {
		await page.goto('/lms/membership-plans')
		await expect(page.getByRole('heading', { name: 'Choose Your Plan' })).toBeVisible()
		await page.getByRole('button', { name: /^Individual$/ }).click()
		await page.waitForTimeout(300)
		await shot(page, '03-guest-plans-individual')
	})

	test('04 /c/<slug> course landing', async ({ page }) => {
		await page.goto(`/c/${FREE_COURSE_SLUG}`)
		await expect(page.locator('h1').first()).toBeVisible()
		await shot(page, '04-guest-course-landing')
	})

	test('05 /c/<slug> with RegisterModal open', async ({ page }) => {
		await page.goto(`/c/${FREE_COURSE_SLUG}`)
		await page.locator('[data-action="open-register"]').first().click()
		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
		await shot(page, '05-guest-course-modal')
	})

	test('06 /e/<slug> event landing', async ({ page }) => {
		await page.goto(`/e/${EVENT_SLUG}`)
		await expect(page.locator('h1').first()).toBeVisible()
		await shot(page, '06-guest-event-landing')
	})

	test('07 /e/<slug> with existing-email pivot to Log In tab', async ({ page }) => {
		await page.goto(`/e/${EVENT_SLUG}`)
		await page.locator('[data-action="open-register"]').first().click()
		await page.locator('#register-modal-signup input[name="full_name"]').fill('Walkthrough Test')
		await page.locator('#register-modal-signup input[name="email"]').fill('pro@test.com')
		await page.locator('#register-modal-signup input[name="password"]').fill('TestUser@2026!')
		await page.locator('#register-modal-signup button[type="submit"]').click()
		await expect(page.getByText('That email is already registered')).toBeVisible({ timeout: 10000 })
		await shot(page, '07-guest-event-modal-exists-pivot')
	})
})

test.describe('Visual walkthrough — logged in', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/login')
		await page.fill('#login_email', 'pro@test.com')
		await page.fill('#login_password', 'TestUser@2026!')
		await page.click('.btn-login')
		await page.waitForURL('**/lms/**', { timeout: 15000 })
	})

	test('08 /lms dashboard', async ({ page }) => {
		await page.goto('/lms')
		await expect(page.locator('div.bg-surface-menu-bar').first()).toBeVisible()
		await shot(page, '08-loggedin-dashboard')
	})

	test('09 /lms/membership-plans (logged in)', async ({ page }) => {
		await page.goto('/lms/membership-plans')
		await expect(page.getByRole('heading', { name: 'Choose Your Plan' })).toBeVisible()
		await expect(page.locator('div.bg-surface-menu-bar').first()).toBeVisible()
		await shot(page, '09-loggedin-plans')
	})

	test('10 /lms/events admin list (logged in)', async ({ page }) => {
		await page.goto('/lms/events')
		await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
		await shot(page, '10-loggedin-events-list')
	})

	test('11 /lms/events/<slug> detail with public-URL chip', async ({ page }) => {
		await page.goto(`/lms/events/${EVENT_SLUG}`)
		await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
		await shot(page, '11-loggedin-event-detail')
	})
})
