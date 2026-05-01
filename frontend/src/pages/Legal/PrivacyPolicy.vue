<template>
	<LegalPage
		:title="__('Privacy Policy')"
		:lastUpdated="__('May 1, 2026')"
		routeName="PrivacyPolicy"
	>
		<p>
			PPT4ed (&ldquo;we,&rdquo; &ldquo;our,&rdquo; or &ldquo;us&rdquo;) operates this learning
			management platform to deliver continuing education courses, events, and
			certificates to professionals. This Privacy Policy explains what
			information we collect, how we use it, and the choices you have.
		</p>

		<h2>Information we collect</h2>
		<p>We collect the following categories of information:</p>
		<ul>
			<li>
				<strong>Account information</strong> — name, email address, and an
				optional professional license number, license type, and license
				jurisdiction that you provide to assist with continuing-education
				reporting.
			</li>
			<li>
				<strong>Course and event activity</strong> — courses you enroll in,
				lessons completed, quiz attempts, event registrations, certificates
				earned, and feedback survey responses.
			</li>
			<li>
				<strong>Payment information</strong> — payments are processed by
				Stripe. We never see or store your full card number or bank account
				details. We do retain transaction metadata (amount, currency, last
				four digits, payment status) returned by Stripe.
			</li>
			<li>
				<strong>Company membership data</strong> — if your employer
				administers a company account, the company administrator can see your
				enrollment status, completion progress, and certificates earned
				through company-allocated credits.
			</li>
			<li>
				<strong>Email engagement</strong> — when we send transactional emails
				(course invitations, event reminders, certificate notifications) we
				may track delivery status through our email provider.
			</li>
			<li>
				<strong>Technical data</strong> — IP address, browser type, device
				information, and timestamps, retained for security, fraud prevention,
				and debugging.
			</li>
		</ul>

		<h2>How we use your information</h2>
		<ul>
			<li>To provide access to courses, events, resources, and certificates.</li>
			<li>To process payments and credit allocations through Stripe.</li>
			<li>
				To send transactional emails (enrollment confirmations, event
				reminders, certificate issuance, two-factor authentication codes,
				announcements from instructors).
			</li>
			<li>To enforce two-factor authentication on every login.</li>
			<li>
				To provide your employer&rsquo;s company administrator with visibility
				into team activity when you participate via a company account.
			</li>
			<li>
				To improve the platform, debug issues, and protect against abuse.
			</li>
			<li>To comply with legal obligations.</li>
		</ul>

		<h2>Service providers</h2>
		<p>
			We share limited information with the following service providers, each
			under their own privacy commitments:
		</p>
		<ul>
			<li>
				<strong>Stripe</strong> — payment processing for one-off course
				purchases, event registrations, and credit purchases.
			</li>
			<li>
				<strong>Resend</strong> — outbound email delivery for transactional
				notifications.
			</li>
			<li>
				<strong>DigitalOcean</strong> — cloud infrastructure that hosts the
				platform.
			</li>
		</ul>
		<p>
			We do not sell your personal information, and we do not share it with
			advertising networks.
		</p>

		<h2>Your choices</h2>
		<ul>
			<li>
				<strong>Access and correction</strong> — you can view and edit your
				profile information at any time from your account settings.
			</li>
			<li>
				<strong>Deletion</strong> — to request deletion of your account and
				associated personal data, contact
				<a href="mailto:support@ppt4ed.org">support@ppt4ed.org</a>. Note that
				we may retain transaction records and issued certificates for legal,
				tax, and continuing-education compliance purposes.
			</li>
			<li>
				<strong>Email preferences</strong> — transactional emails (login
				codes, payment receipts, certificate notices) cannot be disabled
				while your account is active.
			</li>
		</ul>

		<h2>Security</h2>
		<p>
			We use HTTPS for all traffic, encrypt sensitive data in transit, and
			restrict access to production systems. No system is perfectly secure;
			please use a strong, unique password and keep your two-factor
			authentication device safe.
		</p>

		<h2>Children</h2>
		<p>
			This platform is intended for adult professionals. We do not knowingly
			collect personal information from children under 13.
		</p>

		<h2>Changes to this policy</h2>
		<p>
			We may update this policy from time to time. The &ldquo;Last updated&rdquo;
			date at the top reflects the most recent revision. Material changes will
			be communicated by email to active account holders.
		</p>
	</LegalPage>
</template>

<script setup>
import LegalPage from '@/pages/Legal/LegalPage.vue'
</script>
