<template>
	<div class="p-5 max-w-xl">
		<div v-if="company.data" class="space-y-6">
			<div class="space-y-4">
				<h3 class="text-sm font-medium text-ink-gray-5 uppercase tracking-wide">
					{{ __('Company Settings') }}
				</h3>

				<div class="space-y-4">
					<div>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Status') }}
						</label>
						<FormControl
							v-model="form.status"
							type="select"
							:options="['Active', 'Suspended', 'Cancelled']"
						/>
					</div>

					<div>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Billing Email') }}
						</label>
						<FormControl
							v-model="form.billing_email"
							type="email"
							:placeholder="__('billing@company.com')"
						/>
					</div>

					<div>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Max Seats') }}
						</label>
						<FormControl
							v-model="form.max_seats"
							type="number"
							:placeholder="__('10')"
						/>
					</div>
				</div>

				<Button
					variant="solid"
					:loading="updateResource.loading"
					@click="saveChanges"
				>
					{{ __('Save') }}
				</Button>
			</div>

			<div v-if="company.data.membership" class="rounded-lg border p-5 space-y-3">
				<h3 class="text-sm font-medium text-ink-gray-5 uppercase tracking-wide">
					{{ __('Membership') }}
				</h3>
				<div class="grid grid-cols-2 gap-3 text-sm">
					<div>
						<p class="text-ink-gray-5">{{ __('Plan') }}</p>
						<p class="font-medium text-ink-gray-9">{{ company.data.membership.plan }}</p>
					</div>
					<div>
						<p class="text-ink-gray-5">{{ __('Status') }}</p>
						<Badge
							:theme="company.data.membership.status === 'Active' ? 'green' : 'orange'"
						>
							{{ company.data.membership.status }}
						</Badge>
					</div>
					<div>
						<p class="text-ink-gray-5">{{ __('Credit Balance') }}</p>
						<p class="font-medium text-ink-gray-9">{{ company.data.membership.credit_balance }}</p>
					</div>
					<div v-if="company.data.membership.stripe_subscription_id">
						<p class="text-ink-gray-5">{{ __('Stripe Subscription') }}</p>
						<p class="font-mono text-xs text-ink-gray-7">{{ company.data.membership.stripe_subscription_id }}</p>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Badge, Button, FormControl, createResource, toast } from 'frappe-ui'

const props = defineProps({
	company: {
		type: Object,
		required: true,
	},
})

const form = ref({
	status: '',
	billing_email: '',
	max_seats: 0,
})

watch(
	() => props.company.data,
	(data) => {
		if (data) {
			form.value.status = data.status || 'Active'
			form.value.billing_email = data.billing_email || ''
			form.value.max_seats = data.max_seats || 0
		}
	},
	{ immediate: true }
)

const updateResource = createResource({
	url: 'lms.lms.ceu_admin.admin_update_company',
	onSuccess() {
		toast({ title: __('Saved'), icon: 'check', iconClasses: 'text-green-500' })
		props.company.reload()
	},
	onError(err) {
		toast({ title: __('Error'), text: err.message, icon: 'x', iconClasses: 'text-red-500' })
	},
})

const saveChanges = () => {
	updateResource.submit({
		company: props.company.data.name,
		status: form.value.status,
		billing_email: form.value.billing_email,
		max_seats: form.value.max_seats,
	})
}
</script>
