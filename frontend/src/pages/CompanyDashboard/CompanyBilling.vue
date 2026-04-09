<template>
	<div class="p-5">
		<div v-if="dashboard.data?.membership" class="space-y-6">
			<div class="rounded-lg border p-5">
				<h3 class="text-sm font-medium text-ink-gray-5 mb-3">
					{{ __('Current Plan') }}
				</h3>
				<div class="flex items-center justify-between">
					<div>
						<p class="text-lg font-semibold text-ink-gray-9">
							{{ dashboard.data.membership.plan }}
						</p>
						<p class="text-sm text-ink-gray-5 mt-1">
							{{ dashboard.data.membership.credit_balance }} {{ __('credits remaining') }}
						</p>
					</div>
					<Badge
						:theme="dashboard.data.membership.status === 'Active' ? 'green' : 'orange'"
					>
						{{ dashboard.data.membership.status }}
					</Badge>
				</div>
			</div>

			<Button
				v-if="dashboard.data.membership.stripe_customer_id"
				variant="outline"
				:loading="portalUrl.loading"
				@click="openBillingPortal"
			>
				{{ __('Manage Billing in Stripe') }}
			</Button>
		</div>
		<div v-else-if="dashboard.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			<p>{{ __('No active membership.') }}</p>
			<p class="mt-2 text-sm">
				{{ __('Contact support to set up a company membership plan.') }}
			</p>
		</div>
	</div>
</template>

<script setup>
import { Badge, Button, createResource } from 'frappe-ui'

const dashboard = createResource({
	url: 'lms.lms.ceu_company_dashboard.get_company_dashboard',
	cache: ['company-dashboard'],
	auto: true,
})

const portalUrl = createResource({
	url: 'lms.lms.ceu_stripe.get_customer_portal_url',
	onSuccess(data) {
		window.open(data.url, '_blank')
	},
})

const openBillingPortal = () => {
	if (dashboard.data?.membership?.name) {
		portalUrl.submit({ membership_name: dashboard.data.membership.name })
	}
}
</script>
