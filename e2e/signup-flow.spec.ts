import { test, expect, Page } from '@playwright/test'

/**
 * Public signup flow — covers the four entry points wired up to
 * `lms.lms.api.signup_and_enroll`:
 *   1. /lms/signup        (top-of-funnel)
 *   2. /c/<slug>          (Jinja course landing → register modal)
 *   3. /e/<slug>          (Jinja event landing → register modal)
 *   4. /lms/membership-plans → RegisterModal with intent='membership:<plan>'
 *
 * NOTE: each test uses a fresh `signup-test+<uuid>@example.com` so reruns
 * never collide with state from prior runs. Cleanup is out of band — devlms
 * is the test environment, not prod.
 *
 * TEST DATA assumed on devlms:
 *   - FREE_COURSE_SLUG must be a published, free LMS Course
 *   - PAID_EVENT_SLUG must be a published, paid LMS Event
 *   - PAID_PLAN_NAME must be an active, purchasable CEU Membership Plan
 *   - Update these constants when the seed data changes.
 */

const FREE_COURSE_SLUG =
	'the-power-of-play-linking-play-to-language-cognitive-social-emotional-literacy-development'
const PAID_EVENT_SLUG = 'pediatric-adaptive-equipment-evaluation-and-fitting'
const PAID_PLAN_NAME = 'Individual Professional'
const PAID_COURSE_SLUG =
	'catch-the-wave-introduction-to-whole-body-vibration-in-pediatric-therapy-for-pts-ots-and-slps'

function pptEmail(): string {
	const stamp = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
	return `signup-test+${stamp}@ppt4kids.com`
}

function uniqueEmail(): string {
	const stamp = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
	return `signup-test+${stamp}@example.com`
}

function password(): string {
	return 'TestUser@2026!'
}

async function fillSignupModal(page: Page, email: string, fullName: string) {
	// RegisterModal.vue Dialog uses frappe-ui FormControl. Inputs are matched
	// by their visible label since FormControl wraps inputs in a structured way.
	await page.getByLabel('Full name').fill(fullName)
	await page.getByLabel('Email').fill(email)
	await page.getByLabel('Password').fill(password())
}

test.describe('Public signup flow', () => {
	test('1. /signup creates a free account and lands on dashboard with upsell banner', async ({ page }) => {
		const email = uniqueEmail()

		await page.goto('/lms/signup')
		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()

		await page.getByLabel('Full name').fill('Signup Test One')
		await page.getByLabel('Email').fill(email)
		await page.getByLabel('Password').fill(password())
		await page.getByRole('button', { name: 'Create account' }).click()

		// signup_and_enroll(intent='free') with no target → redirect_to=/lms
		await page.waitForURL('**/lms', { timeout: 15000 })

		// Greeting should render with the new user's name
		await expect(page.locator('.text-xl.font-bold')).toContainText('Signup Test One')

		// Upsell banner: free user (no company, no membership) sees it on first visit
		await expect(page.getByText('Unlock more courses')).toBeVisible()
		await expect(page.getByRole('link', { name: /See plans/ })).toBeVisible()
	})

	test('2. Course landing → register modal → free enrollment', async ({ page }) => {
		const email = uniqueEmail()

		await page.goto(`/c/${FREE_COURSE_SLUG}`)
		// Sticky CTA on the right rail; Jinja landing renders `data-action="open-register"`
		await page.locator('[data-action="open-register"]').first().click()

		// Modal opens; defaults to signup tab
		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()

		await fillSignupModal(page, email, 'Signup Test Two')
		await page.getByRole('button', { name: 'Create account' }).click()

		// Free course → enrolled → /lms/courses/<slug>
		await page.waitForURL(`**/lms/courses/${FREE_COURSE_SLUG}**`, { timeout: 20000 })
	})

	test('3. Event landing → register modal → paid checkout redirects to Stripe', async ({ page }) => {
		const email = uniqueEmail()

		await page.goto(`/e/${PAID_EVENT_SLUG}`)
		await page.locator('[data-action="open-register"]').first().click()

		await fillSignupModal(page, email, 'Signup Test Three')

		// Submit, then wait for navigation to Stripe Checkout
		await Promise.all([
			page.waitForURL(/checkout\.stripe\.com/, { timeout: 25000 }),
			page.getByRole('button', { name: /Continue to checkout|Create account/ }).click(),
		])

		expect(page.url()).toContain('checkout.stripe.com')
	})

	test('4. MembershipPlans (logged out) → Stripe via subscription intent', async ({ page }) => {
		const email = uniqueEmail()

		await page.goto('/lms/membership-plans')

		// Click any plan's "Get Started" button. We rely on the first matching CTA;
		// real test data may need to switch the Individual tab depending on the
		// seed plan layout — adjust if the first CTA is on the Company tab.
		const getStarted = page.getByRole('button', { name: 'Get Started' }).first()
		await getStarted.click()

		// RegisterModal opens
		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()

		await fillSignupModal(page, email, 'Signup Test Four')

		await Promise.all([
			page.waitForURL(/checkout\.stripe\.com/, { timeout: 25000 }),
			page.getByRole('button', { name: /Continue to checkout|Create account/ }).click(),
		])

		expect(page.url()).toContain('checkout.stripe.com')
	})

	test('5. Existing email pivots Register modal to Log In tab with email prefilled', async ({ page }) => {
		// First create a fresh user via /signup, then log out and revisit a
		// course landing — submitting the same email should surface the
		// "already registered" pivot.
		const email = uniqueEmail()

		await page.goto('/lms/signup')
		await page.getByLabel('Full name').fill('Signup Test Five')
		await page.getByLabel('Email').fill(email)
		await page.getByLabel('Password').fill(password())
		await page.getByRole('button', { name: 'Create account' }).click()
		await page.waitForURL('**/lms', { timeout: 15000 })

		// Log out so we land on the Jinja landing as a guest
		await page.goto('/api/method/logout')
		await page.waitForLoadState('networkidle')

		await page.goto(`/c/${FREE_COURSE_SLUG}`)
		await page.locator('[data-action="open-register"]').first().click()

		await fillSignupModal(page, email, 'Signup Test Five')
		await page.getByRole('button', { name: 'Create account' }).click()

		// Modal pivots to Log In tab with email prefilled
		await expect(page.getByText('That email is already registered')).toBeVisible({ timeout: 10000 })
		const emailField = page.getByLabel('Email')
		await expect(emailField).toHaveValue(email)
		await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible()
	})

	test('6a. @ppt4kids.com signup on paid event lands free, NOT on Stripe', async ({ page }) => {
		// Regression: pre-fix the public Register modal routed every signer to
		// Stripe regardless of email domain. PPT staff were getting the paywall
		// from public event landings. See PR #166.
		const email = pptEmail()

		await page.goto(`/e/${PAID_EVENT_SLUG}`)
		await page.locator('[data-action="open-register"]').first().click()

		// Scope by `name=` because the Jinja modal keeps both signup + login
		// forms in DOM (`hidden` on login), so getByLabel('Email') is ambiguous.
		const signup = page.locator('#register-modal-signup')
		await signup.locator('input[name="full_name"]').fill('PPT Kids Event')
		await signup.locator('input[name="email"]').fill(email)
		await signup.locator('input[name="password"]').fill(password())
		await signup.locator('button[type="submit"]').click()

		// Should land on the in-app event page, free-registered.
		await page.waitForURL(`**/lms/events/${PAID_EVENT_SLUG}**`, { timeout: 20000 })
		expect(page.url()).not.toContain('checkout.stripe.com')
	})

	test('6b. @ppt4kids.com signup on paid course lands free, NOT on Stripe', async ({ page }) => {
		const email = pptEmail()

		await page.goto(`/c/${PAID_COURSE_SLUG}`)
		await page.locator('[data-action="open-register"]').first().click()

		const signup = page.locator('#register-modal-signup')
		await signup.locator('input[name="full_name"]').fill('PPT Kids Course')
		await signup.locator('input[name="email"]').fill(email)
		await signup.locator('input[name="password"]').fill(password())
		await signup.locator('button[type="submit"]').click()

		await page.waitForURL(`**/lms/courses/${PAID_COURSE_SLUG}**`, { timeout: 20000 })
		expect(page.url()).not.toContain('checkout.stripe.com')
	})

	test('7. Signup bypasses 2FA on first session; subsequent login still gates', async ({ page }) => {
		// 2FA enforcement on devlms is the production model: the freshly-created
		// session is exempt (login_as path), but the next /login attempt should
		// behave like any other login. We do not assert OTP UI here because OTP
		// delivery is environment-specific — instead we assert that signup landed
		// us on /lms (no OTP prompt) and that /login renders the standard form
		// for the same user afterwards.
		const email = uniqueEmail()

		await page.goto('/lms/signup')
		await page.getByLabel('Full name').fill('Signup Test Six')
		await page.getByLabel('Email').fill(email)
		await page.getByLabel('Password').fill(password())
		await page.getByRole('button', { name: 'Create account' }).click()

		// The fact that we land on /lms (and not on a 2FA challenge URL) is the
		// 2FA-bypass assertion for the first session.
		await page.waitForURL('**/lms', { timeout: 15000 })
		expect(page.url()).not.toContain('two_factor')

		// Log out, then attempt to log in fresh — should reach the login form,
		// not auto-bypass.
		await page.goto('/api/method/logout')
		await page.waitForLoadState('networkidle')
		await page.goto('/login')
		await expect(page.locator('#login_email')).toBeVisible()
	})
})
