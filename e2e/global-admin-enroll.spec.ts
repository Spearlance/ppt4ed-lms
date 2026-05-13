import { test, expect, Page } from '@playwright/test'

/**
 * Smoke tests for PR #96: Global Admins should see Enroll / Register /
 * Claim buttons on courses, events, and resources they don't teach,
 * AND the Free plan card on /lms/membership-plans should show the new
 * pay-as-you-go copy.
 *
 * Runs against devlms.ppt4ed.org with a dedicated test user that has
 * the Global Admin role. The user is seeded out-of-band (see thread
 * notes) and is NOT an instructor of any course/event/resource on dev.
 */

const ADMIN_EMAIL = 'global-admin@test.com'
const ADMIN_PASSWORD = 'TestUser@2026!'

const PAID_COURSE_SLUG =
	'the-power-of-play-linking-play-to-language-cognitive-social-emotional-literacy-development'
const EVENT_SLUG = 'pediatric-adaptive-equipment-evaluation-and-fitting'
const RESOURCE_SLUG = 'supporting-families-through-the-referral-process'

async function loginAsGlobalAdmin(page: Page) {
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

test.describe('PR #96 — Global Admin enroll / register / claim', () => {
	test('Global Admin sees "Buy this course" on a paid course they do not teach', async ({
		page,
	}) => {
		await loginAsGlobalAdmin(page)
		await page.goto(`/lms/courses/${PAID_COURSE_SLUG}`)

		// Admin lands in the Tabs view (parent Detail.vue isAdmin path).
		// The first tab is Overview → CourseOverview → CourseCardOverlay,
		// which is where the enroll/buy button lives. Pre-PR #96 this was
		// hidden because the overlay-level isAdmin included is_moderator.
		await expect(page.getByRole('button', { name: 'Buy this course' })).toBeVisible({
			timeout: 15000,
		})

		await logout(page)
	})

	test('Global Admin sees Register/Enroll button on an event they do not teach', async ({
		page,
	}) => {
		await loginAsGlobalAdmin(page)
		await page.goto(`/lms/events/${EVENT_SLUG}`)

		// EventOverlay renders one of: "Register Now" (paid, with seats),
		// "Enroll Now" (free, allow_self_enrollment). Pre-PR #96 both were
		// hidden behind canAccessEvent which included isModerator. Now
		// canAccessEvent only includes actual instructors + registered
		// students for the register-button gate, so admins see one or the
		// other depending on event configuration.
		const registerBtn = page.getByRole('button', { name: 'Register Now' })
		const enrollBtn = page.getByRole('button', { name: 'Enroll Now' })

		await expect(registerBtn.or(enrollBtn).first()).toBeVisible({ timeout: 15000 })

		await logout(page)
	})

	test('Global Admin sees "Claim this Resource" on a resource they have not claimed', async ({
		page,
	}) => {
		await loginAsGlobalAdmin(page)
		await page.goto(`/lms/resources/${RESOURCE_SLUG}`)

		// ResourceCardOverlay used to gate the Claim button behind
		// isAdmin = is_moderator || isInstructor. Now it's just
		// isInstructor of THIS resource, so global admins (who aren't
		// listed as instructors) see Claim. If the run-once test user
		// has already claimed in a previous run, the button collapses
		// to "Continue Learning"; treat either as a pass.
		const claim = page.getByRole('button', { name: 'Claim this Resource' })
		const continueLearning = page.getByRole('button', { name: 'Continue Learning' })

		await expect(claim.or(continueLearning).first()).toBeVisible({ timeout: 15000 })

		await logout(page)
	})

	test('Membership Plans free tier: new pay-as-you-go copy renders', async ({ page }) => {
		// Public page, no login required.
		await page.goto('/lms/membership-plans')

		await page.getByRole('button', { name: /^Individual$/ }).click()

		// New copy from PR #96 (replaces "Free courses, no commitment").
		await expect(
			page.getByText('Free resources. Pay-as-you-go for CEU courses.')
		).toBeVisible({ timeout: 10000 })

		// Old copy should be gone.
		await expect(page.getByText('Free courses, no commitment')).toHaveCount(0)
	})
})
