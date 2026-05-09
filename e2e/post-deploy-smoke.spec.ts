import { test, expect, Page } from '@playwright/test'

/**
 * Post-deploy smoke covering the three fixes from PR #68 plus the
 * underlying public landings shipped in PRs #65–#67. Runs against the
 * live devlms.ppt4ed.org. No user state is created or modified.
 */

const FREE_COURSE_SLUG =
	'the-power-of-play-linking-play-to-language-cognitive-social-emotional-literacy-development'
const EVENT_SLUG = 'pediatric-adaptive-equipment-evaluation-and-fitting'

async function expectImageRenders(page: Page, locator: string) {
	const img = page.locator(locator)
	await expect(img).toBeVisible()
	const dims = await img.evaluate((el: HTMLImageElement) => ({
		w: el.naturalWidth,
		h: el.naturalHeight,
		src: el.src,
	}))
	expect(dims.src, 'img src should not be [object Object]').not.toContain('[object Object]')
	expect(dims.w, `img naturalWidth must be > 0 (was ${dims.w}, src=${dims.src})`).toBeGreaterThan(0)
	expect(dims.h, `img naturalHeight must be > 0 (was ${dims.h}, src=${dims.src})`).toBeGreaterThan(0)
}

test.describe('Post-deploy smoke (PR #68)', () => {
	test('membership plans: Free card visible on Individual tab, PPT Employee hidden', async ({ page }) => {
		await page.goto('/lms/membership-plans')

		// Default tab is Company; switch to Individual.
		await page.getByRole('button', { name: /^Individual$/ }).click()

		// Free card present
		const freeCard = page.locator('h3:text("Free")').first()
		await expect(freeCard).toBeVisible()

		// "Browse" badge on the Free card (distinguishes from real plans)
		await expect(page.locator('text=Browse').first()).toBeVisible()

		// $0 price on the Free card
		await expect(page.getByText('$0').first()).toBeVisible()

		// At least one paid Individual plan card exists alongside Free
		// (Professional Membership or Individual Business Membership)
		const paidCardTitles = await page
			.locator('h3.text-lg.font-semibold')
			.allTextContents()
		const hasPaid = paidCardTitles.some((t) =>
			/Professional Membership|Individual Business Membership|Educational Partner/i.test(t)
		)
		expect(hasPaid, `Expected at least one paid Individual plan; saw ${JSON.stringify(paidCardTitles)}`).toBe(true)

		// PPT Employee plan must not appear anywhere on the page
		const bodyText = await page.locator('body').innerText()
		expect(bodyText).not.toMatch(/PPT Employee/)
	})

	test('signup page: PPT4ed logo image renders with non-empty natural dimensions', async ({ page }) => {
		await page.goto('/lms/signup')

		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()

		// Target the Signup card's hero logo specifically — the AppSidebar
		// also renders an <img> for the brand button, so a bare locator('img')
		// would be ambiguous. The Signup hero logo has class `mx-auto h-10`.
		const heroLogo = 'img.mx-auto.h-10'
		await page.locator(heroLogo).waitFor({ state: 'visible', timeout: 8000 })

		await expectImageRenders(page, heroLogo)
	})

	test('course landing /c/<slug> renders with guest register CTA', async ({ page }) => {
		await page.goto(`/c/${FREE_COURSE_SLUG}`)

		// Hero copy + outline are server-rendered
		await expect(page).toHaveTitle(/Power of Play/i)
		await expect(page.locator('h1').first()).toContainText(/Power of Play/i)

		// At least one register-modal trigger
		const cta = page.locator('[data-action="open-register"]').first()
		await expect(cta).toBeVisible()

		// Clicking opens the modal
		await cta.click()
		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()

		// Email field is empty (no prefill on first open) and Log In tab is reachable
		await expect(page.locator('#register-modal-signup input[name="email"]')).toHaveValue('')
		await page.getByRole('tab', { name: 'Log in' }).click()
		await expect(page.locator('#register-modal-login input[name="usr"]')).toBeVisible()
	})

	test('event landing /e/<slug> renders with schedule + guest register CTA', async ({ page }) => {
		await page.goto(`/e/${EVENT_SLUG}`)

		await expect(page.locator('h1').first()).toContainText(/Pediatric Adaptive Equipment/i)

		// Schedule section emitted (multi-day or single-day)
		await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible()

		// Register modal trigger present
		await expect(page.locator('[data-action="open-register"]').first()).toBeVisible()
	})

	test('AppSidebar is hidden on guest-allowed Vue pages (signup, membership-plans)', async ({ page }) => {
		// AppSidebar's root carries `bg-surface-menu-bar`; NoSidebarLayout
		// doesn't render any element with that class.
		const sidebar = 'div.bg-surface-menu-bar'

		await page.goto('/lms/signup')
		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
		await expect(page.locator(sidebar)).toHaveCount(0)

		await page.goto('/lms/membership-plans')
		await expect(page.getByRole('heading', { name: 'Choose Your Plan' })).toBeVisible()
		await expect(page.locator(sidebar)).toHaveCount(0)
	})

	test('AppSidebar IS visible for logged-in users (regression test for #69)', async ({ page }) => {
		// PR #69 originally shipped a broken layout selector — the Pinia
		// destructure unwrapped `isLoggedIn` to a plain boolean, so
		// `isLoggedIn.value` was undefined and `!isLoggedIn.value` was
		// always true. Every logged-in user got NoSidebarLayout. Don't
		// regress.
		await page.goto('/login')
		await page.fill('#login_email', 'pro@test.com')
		await page.fill('#login_password', 'TestUser@2026!')
		await page.click('.btn-login')
		await page.waitForURL('**/lms/**', { timeout: 15000 })

		// Sidebar root must render now that we're authenticated
		await expect(page.locator('div.bg-surface-menu-bar').first()).toBeVisible({ timeout: 10000 })

		// Clean up so subsequent tests start as a guest
		await page.goto('/api/method/logout')
		await page.waitForLoadState('networkidle')
	})

	test('EditProfile: signature_text persists across save (PR #76)', async ({ page }) => {
		// Logs in as the seeded pro user (sarah / pro@test.com), opens
		// EditProfile from /lms/user/sarah, sets a unique Signature value,
		// saves, reloads, and asserts the value round-trips. The Signature
		// field is the new typed-cursive replacement for the deprecated
		// signature_image attach field.
		const SIG_VALUE = `E2E Sig ${Date.now()}`

		await page.goto('/login')
		await page.fill('#login_email', 'pro@test.com')
		await page.fill('#login_password', 'TestUser@2026!')
		await page.click('.btn-login')
		await page.waitForURL('**/lms/**', { timeout: 15000 })

		await page.goto('/lms/user/sarah')
		await page.getByRole('button', { name: 'Edit Profile' }).click()

		const dialog = page.getByRole('dialog')
		await expect(dialog.getByText('Edit Profile').first()).toBeVisible()

		const sigInput = dialog.getByLabel('Signature', { exact: true })
		await sigInput.fill(SIG_VALUE)

		// "Save" button lives in the dialog's body-header
		await dialog.getByRole('button', { name: 'Save' }).click()
		await expect(dialog).toBeHidden({ timeout: 10000 })

		// Re-open the modal and assert the value persisted
		await page.getByRole('button', { name: 'Edit Profile' }).click()
		const reopened = page.getByRole('dialog')
		await expect(reopened.getByText('Edit Profile').first()).toBeVisible()
		await expect(reopened.getByLabel('Signature', { exact: true })).toHaveValue(SIG_VALUE)

		// Cleanup so the field doesn't leak across runs
		await reopened.getByLabel('Signature', { exact: true }).fill('')
		await reopened.getByRole('button', { name: 'Save' }).click()
		await expect(reopened).toBeHidden({ timeout: 10000 })

		// Logout so subsequent guest-only tests start clean
		await page.goto('/api/method/logout')
		await page.waitForLoadState('networkidle')
	})

	test('event landing modal: submitting an existing email pivots to Log In tab', async ({ page }) => {
		// Uses a known seeded user from company-employee.spec.ts:
		//   pro@test.com / TestUser@2026!
		// The modal should reject signup with "exists" status and pivot.
		await page.goto(`/e/${EVENT_SLUG}`)
		await page.locator('[data-action="open-register"]').first().click()

		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()

		// Fill the signup form with an email that already exists
		await page.locator('#register-modal-signup input[name="full_name"]').fill('Smoke Test')
		await page.locator('#register-modal-signup input[name="email"]').fill('pro@test.com')
		await page.locator('#register-modal-signup input[name="password"]').fill('TestUser@2026!')
		await page.locator('#register-modal-signup button[type="submit"]').click()

		// Modal pivots to Log In tab with email prefilled
		await expect(page.getByText('That email is already registered')).toBeVisible({ timeout: 10000 })
		await expect(page.locator('#register-modal-login input[name="usr"]')).toHaveValue('pro@test.com')
	})
})

test.describe('Free Resources claim flow', () => {
	// A single-lesson Video resource whose lesson body is an EditorJS blob
	// containing a YouTube embed — the canonical case that broke before
	// `enablePlyr()` was wired into ResourceOverview. Replace if the slug
	// is ever deleted; any single-lesson video Resource with EditorJS
	// content works.
	const RESOURCE_SLUG = 'supporting-families-through-the-referral-process'

	test('public /r/<slug>: hero renders + "Get this resource" modal trigger is present', async ({ page }) => {
		await page.goto(`/r/${RESOURCE_SLUG}`)

		await expect(page.locator('h1').first()).toContainText(/Supporting Families/i)
		await expect(page.getByRole('button', { name: /Get this resource/i })).toBeVisible()

		// Modal isn't open until the trigger fires; once it does we should see
		// the standard signup pane.
		await page.getByRole('button', { name: /Get this resource/i }).click()
		await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
	})

	test('modal signup happy-path: fresh user lands on /lms/resources/<slug> already claimed', async ({ page }) => {
		// Unique email per run so the signup actually creates a user. These
		// linger in the DB; they're easy to spot (suffix `@e2e.invalid`).
		const email = `claim-smoke-${Date.now()}@e2e.invalid`
		const password = 'ClaimSmoke@2026!'

		await page.goto(`/r/${RESOURCE_SLUG}`)
		await page.getByRole('button', { name: /Get this resource/i }).click()

		await page.locator('#register-modal-signup input[name="full_name"]').fill('Claim Smoke')
		await page.locator('#register-modal-signup input[name="email"]').fill(email)
		await page.locator('#register-modal-signup input[name="password"]').fill(password)
		await page.locator('#register-modal-signup button[type="submit"]').click()

		// signup_and_enroll auto-claims the resource and redirects into the
		// in-app view. The Vue page should then render the lesson content
		// without the "Claim this Resource" button (already claimed).
		await page.waitForURL(`**/lms/resources/${RESOURCE_SLUG}`, { timeout: 20000 })
		await expect(page.locator('h1').first()).toContainText(/Supporting Families/i)
		await expect(page.getByRole('button', { name: 'Claim this Resource' })).toHaveCount(0)

		// The whole reason this PR exists: the YouTube embed must actually
		// render. Plyr swaps the placeholder div for an iframe.
		await expect(page.locator('iframe[src*="youtube"]').first()).toBeVisible({ timeout: 15000 })

		// Logout so subsequent tests start clean
		await page.goto('/api/method/logout')
		await page.waitForLoadState('networkidle')
	})

	test('logged-in user on a claimed resource sees content + Plyr-hydrated YouTube iframe', async ({ page }) => {
		// Regression for the original blank-video bug — pro@test.com has
		// been claimed against this resource since the populate script ran,
		// so this just exercises the claimed render path.
		await page.goto('/login')
		await page.fill('#login_email', 'pro@test.com')
		await page.fill('#login_password', 'TestUser@2026!')
		await page.click('.btn-login')
		await page.waitForURL('**/lms/**', { timeout: 15000 })

		await page.goto(`/lms/resources/${RESOURCE_SLUG}`)

		await expect(page.locator('h1').first()).toContainText(/Supporting Families/i)
		await expect(page.locator('iframe[src*="youtube"]').first()).toBeVisible({ timeout: 15000 })

		// Logout
		await page.goto('/api/method/logout')
		await page.waitForLoadState('networkidle')
	})
})
