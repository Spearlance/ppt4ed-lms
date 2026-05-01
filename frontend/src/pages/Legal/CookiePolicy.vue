<template>
	<LegalPage
		:title="__('Cookie Policy')"
		:lastUpdated="__('May 1, 2026')"
		routeName="CookiePolicy"
	>
		<p>
			This Cookie Policy explains how the PPT4ed learning platform uses
			cookies and similar storage technologies in your browser. It should be
			read together with our
			<router-link :to="{ name: 'PrivacyPolicy' }">Privacy Policy</router-link>.
		</p>

		<h2>What is a cookie?</h2>
		<p>
			A cookie is a small text file that a website stores on your device when
			you visit. Cookies let the site recognise you between page loads and
			between visits. Some are set by the platform itself (first-party); some
			are set by services we embed, such as Stripe (third-party).
		</p>

		<h2>Cookies we set</h2>

		<h3>Strictly necessary</h3>
		<p>
			These cookies are required for the platform to function. You cannot
			disable them without breaking sign-in.
		</p>
		<ul>
			<li>
				<strong>Session</strong> — keeps you logged in as you move between
				pages and persists your two-factor authentication state.
			</li>
			<li>
				<strong>CSRF token</strong> — protects against cross-site request
				forgery on form submissions and API calls.
			</li>
			<li>
				<strong>Sidebar and onboarding state</strong> — remembers whether
				your sidebar is collapsed and which onboarding steps you have
				completed. Stored in browser <code>localStorage</code>, not as a
				traditional cookie.
			</li>
		</ul>

		<h3>Third-party cookies</h3>
		<ul>
			<li>
				<strong>Stripe</strong> — when you proceed to checkout for a course,
				event, or credit purchase, Stripe sets cookies on
				<code>checkout.stripe.com</code> and <code>js.stripe.com</code> for
				fraud prevention and to power their hosted checkout. See
				<a
					href="https://stripe.com/cookie-settings"
					target="_blank"
					rel="noopener noreferrer"
				>Stripe&rsquo;s cookie settings</a>.
			</li>
		</ul>

		<h2>Analytics</h2>
		<p>
			We do not currently use third-party analytics or advertising trackers
			(such as Google Analytics, Facebook Pixel, or LinkedIn Insight Tag) on
			the platform. If that changes, this policy will be updated and active
			users will be notified.
		</p>

		<h2>Managing cookies</h2>
		<p>
			You can clear or block cookies through your browser settings. Blocking
			the strictly-necessary cookies above will prevent you from signing in
			and using the platform. Blocking Stripe cookies will prevent you from
			completing payments.
		</p>

		<h2>Changes to this policy</h2>
		<p>
			Material changes will be reflected in the &ldquo;Last updated&rdquo; date above
			and communicated by email to active account holders.
		</p>
	</LegalPage>
</template>

<script setup>
import LegalPage from '@/pages/Legal/LegalPage.vue'
</script>
