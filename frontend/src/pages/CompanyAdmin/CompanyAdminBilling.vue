<template>
	<div class="p-5">
		<div v-if="company.data?.membership" class="space-y-6">
			<div class="rounded-lg border p-5">
				<h3 class="text-sm font-medium text-ink-gray-5 mb-3">
					{{ __('Current Plan') }}
				</h3>
				<div class="flex items-center justify-between">
					<div>
						<p class="text-lg font-semibold text-ink-gray-9">
							{{ company.data.membership.plan }}
						</p>
						<p class="text-sm text-ink-gray-5 mt-1">
							{{ company.data.membership.credit_balance }} {{ __('credits remaining') }}
						</p>
					</div>
					<Badge
						:theme="company.data.membership.status === 'Active' ? 'green' : 'orange'"
					>
						{{ company.data.membership.status }}
					</Badge>
				</div>
			</div>

			<div v-if="company.data.membership.stripe_customer_id || company.data.membership.stripe_subscription_id" class="rounded-lg border p-5 space-y-3">
				<h3 class="text-sm font-medium text-ink-gray-5 mb-3">
					{{ __('Stripe Details') }}
				</h3>
				<div class="space-y-2 text-sm">
					<div v-if="company.data.membership.stripe_customer_id" class="flex items-center gap-3">
						<span class="text-ink-gray-5 w-36">{{ __('Customer ID') }}</span>
						<span class="font-mono text-ink-gray-7">{{ company.data.membership.stripe_customer_id }}</span>
					</div>
					<div v-if="company.data.membership.stripe_subscription_id" class="flex items-center gap-3">
						<span class="text-ink-gray-5 w-36">{{ __('Subscription ID') }}</span>
						<span class="font-mono text-ink-gray-7">{{ company.data.membership.stripe_subscription_id }}</span>
					</div>
				</div>
			</div>

			<div class="flex items-center gap-3">
				<Button
					v-if="company.data.membership.stripe_customer_id"
					variant="outline"
					@click="openStripe"
				>
					{{ __('View in Stripe') }}
				</Button>
				<Button
					v-if="company.data.membership.status === 'Active'"
					theme="red"
					variant="subtle"
					:loading="cancelResource.loading"
					@click="cancelSubscription"
				>
					{{ __('Cancel Subscription') }}
				</Button>
			</div>
		</div>
		<div v-else-if="company.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			<p>{{ __('No active membership.') }}</p>
			<p class="mt-2 text-sm">
				{{ __('Assign a membership plan to enable billing and credits.') }}
			</p>
		</div>
	</div>
</template>

<script setup>
import { Badge, Button, createResource, toast } from 'frappe-ui'

const props = defineProps({
	company: {
		type: Object,
		required: true,
	},
})

const cancelResource = createResource({
	url: 'lms.lms.ceu_admin.admin_cancel_subscription',
	onSuccess() {
		toast({ title: __('Subscription cancelled'), icon: 'check', iconClasses: 'text-green-500' })
		props.company.reload()
	},
	onError(err) {
		toast({ title: __('Error'), text: err.message, icon: 'x', iconClasses: 'text-red-500' })
	},
})

const openStripe = () => {
	const customerId = props.company.data?.membership?.stripe_customer_id
	if (customerId) {
		window.open(`https://dashboard.stripe.com/customers/${customerId}`, '_blank')
	}
}

const cancelSubscription = () => {
	cancelResource.submit({
		company: props.company.data.name,
	})
}
</script>
