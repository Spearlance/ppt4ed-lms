<template>
	<LegalPage
		:title="__('Terms of Service')"
		:lastUpdated="__('May 1, 2026')"
		routeName="TermsOfService"
	>
		<p>
			These Terms of Service (&ldquo;Terms&rdquo;) govern your access to and use of the
			PPT4ed learning platform (the &ldquo;Service&rdquo;). By creating an account or
			using the Service you agree to these Terms.
		</p>

		<h2>1. Eligibility and accounts</h2>
		<p>
			You must be at least 18 years old to create an account. You agree to
			provide accurate information, including any professional license number
			used for continuing-education reporting, and to keep your account
			credentials confidential. Two-factor authentication is required on every
			login.
		</p>

		<h2>2. Acceptable use</h2>
		<p>You agree not to:</p>
		<ul>
			<li>
				Share your account credentials, certificate, or course content with
				anyone else.
			</li>
			<li>
				Scrape, copy, redistribute, or resell course videos, quizzes,
				resources, or any other materials without written permission.
			</li>
			<li>
				Reverse engineer the platform, attempt to bypass authentication, or
				interfere with platform security.
			</li>
			<li>
				Upload content that is unlawful, infringing, harassing, or otherwise
				objectionable.
			</li>
		</ul>

		<h2>3. Course content and intellectual property</h2>
		<p>
			All courses, events, resources, video lessons, quizzes, and certificate
			templates are the property of PPT4ed or its instructors and are
			licensed, not sold, to you. Your enrollment grants you a personal,
			non-transferable license to access the content for your own
			professional development. The platform source code is licensed
			separately under the GNU Affero General Public License v3
			(<a
				href="https://github.com/Spearlance/ppt4ed-lms"
				target="_blank"
				rel="noopener noreferrer"
			>github.com/Spearlance/ppt4ed-lms</a>).
		</p>

		<h2>4. Payments</h2>
		<p>
			Payments are processed by Stripe. By completing a purchase you authorize
			the charge to your selected payment method. Pricing is shown in U.S.
			dollars at the time of checkout. Continuing-education credits purchased
			by an employer for company team members do not expire.
		</p>

		<h2>5. Refunds</h2>
		<p>
			Refund requests should be sent to
			<a href="mailto:info@ppt4ed.org">info@ppt4ed.org</a>. Refunds are
			at the discretion of PPT4ed and are typically considered when:
		</p>
		<ul>
			<li>The request is made within 7 days of purchase, and</li>
			<li>
				No more than 25% of the course material has been viewed, and no
				certificate has been issued.
			</li>
		</ul>
		<p>
			Event registration refunds may be subject to specific event-level
			policies disclosed at the time of registration. Early-bird and
			promotional pricing is non-refundable beyond the pricing differential.
		</p>

		<h2>6. Certificates</h2>
		<p>
			Certificates are auto-issued upon course completion and submission of
			the post-course feedback survey. Certificates record your name,
			completion date, course title, CEU hours, and applicable disciplines.
			You are responsible for verifying that the certificate satisfies the
			requirements of your licensing board.
		</p>

		<h2>7. Company accounts</h2>
		<p>
			If you join the platform through a company account, your company
			administrator can allocate credits, view your enrollment and completion
			activity, and remove your access. If your company removes you, your
			personal certificates remain accessible to you.
		</p>

		<h2>8. Termination</h2>
		<p>
			You may close your account at any time by contacting support. We may
			suspend or terminate accounts that violate these Terms or that pose a
			security risk to the platform.
		</p>

		<h2>9. Disclaimer of warranties</h2>
		<p>
			The Service is provided &ldquo;as is&rdquo; and &ldquo;as available&rdquo; without warranties
			of any kind, express or implied. We do not warrant that the Service will
			be uninterrupted, error-free, or that course content will satisfy any
			particular jurisdictional requirement.
		</p>

		<h2>10. Limitation of liability</h2>
		<p>
			To the maximum extent permitted by law, PPT4ed will not be liable for
			indirect, incidental, special, or consequential damages arising from
			your use of the Service. Our total liability for any claim arising out
			of or relating to these Terms is limited to the amount you paid to
			PPT4ed in the twelve months preceding the claim.
		</p>

		<h2>11. Changes to these Terms</h2>
		<p>
			We may revise these Terms from time to time. Material changes will be
			communicated by email and reflected in the &ldquo;Last updated&rdquo; date above.
			Continued use of the Service after changes take effect constitutes
			acceptance.
		</p>

		<h2>12. Governing law</h2>
		<p>
			These Terms are governed by the laws of the United States and the state
			in which PPT4ed is incorporated, without regard to conflict-of-law
			principles.
		</p>
	</LegalPage>
</template>

<script setup>
import LegalPage from '@/pages/Legal/LegalPage.vue'
</script>
