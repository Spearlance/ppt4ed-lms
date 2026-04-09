<template>
	<div class="mt-7">
		<div v-if="memberDetails.loading" class="text-sm text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else-if="memberDetails.data" class="space-y-8">
			<!-- Account Type -->
			<div>
				<h2 class="mb-3 text-lg font-semibold text-ink-gray-9">
					{{ __('Account Type') }}
				</h2>
				<Badge
					:label="accountTypeLabel"
					:theme="accountTypeTheme"
					variant="subtle"
					size="md"
				/>
			</div>

			<!-- Membership -->
			<div v-if="memberDetails.data.membership">
				<h2 class="mb-3 text-lg font-semibold text-ink-gray-9">
					{{ __('Membership') }}
				</h2>
				<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
					<div class="bg-surface-gray-1 rounded-md p-3">
						<div class="text-xs text-ink-gray-5 mb-1">{{ __('Plan') }}</div>
						<div class="text-sm font-medium text-ink-gray-9">
							{{ memberDetails.data.membership.plan || '—' }}
						</div>
					</div>
					<div class="bg-surface-gray-1 rounded-md p-3">
						<div class="text-xs text-ink-gray-5 mb-1">{{ __('Status') }}</div>
						<Badge
							:label="memberDetails.data.membership.status"
							:theme="memberDetails.data.membership.status === 'Active' ? 'green' : 'red'"
							variant="subtle"
							size="sm"
						/>
					</div>
					<div class="bg-surface-gray-1 rounded-md p-3">
						<div class="text-xs text-ink-gray-5 mb-1">{{ __('Credits') }}</div>
						<div class="text-sm font-medium text-ink-gray-9">
							{{ memberDetails.data.membership.credit_balance ?? '0' }}
						</div>
					</div>
					<div class="bg-surface-gray-1 rounded-md p-3">
						<div class="text-xs text-ink-gray-5 mb-1">{{ __('Expires') }}</div>
						<div class="text-sm font-medium text-ink-gray-9">
							{{ memberDetails.data.membership.end_date || '—' }}
						</div>
					</div>
				</div>
				<div class="flex flex-wrap gap-2">
					<Button variant="outline" @click="showCreditDialog = true">
						{{ __('Adjust Credits') }}
					</Button>
					<Button
						v-if="memberDetails.data.membership.stripe_subscription_id"
						variant="outline"
						theme="red"
						@click="cancelSubscription()"
					>
						{{ __('Cancel Subscription') }}
					</Button>
					<Button
						v-if="memberDetails.data.membership.stripe_customer_id"
						variant="ghost"
						@click="openStripe()"
					>
						{{ __('View in Stripe') }}
					</Button>
				</div>
			</div>

			<!-- Company -->
			<div>
				<h2 class="mb-3 text-lg font-semibold text-ink-gray-9">
					{{ __('Company') }}
				</h2>
				<div v-if="memberDetails.data.company">
					<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
						<div class="bg-surface-gray-1 rounded-md p-3">
							<div class="text-xs text-ink-gray-5 mb-1">{{ __('Company') }}</div>
							<Link
								:href="`/admin/company/${memberDetails.data.company.name}`"
								class="text-sm font-medium text-ink-blue-3 hover:underline"
							>
								{{ memberDetails.data.company.company_name }}
							</Link>
						</div>
						<div class="bg-surface-gray-1 rounded-md p-3">
							<div class="text-xs text-ink-gray-5 mb-1">{{ __('Role') }}</div>
							<div class="text-sm font-medium text-ink-gray-9">
								{{ memberDetails.data.company.role || '—' }}
							</div>
						</div>
						<div class="bg-surface-gray-1 rounded-md p-3">
							<div class="text-xs text-ink-gray-5 mb-1">{{ __('Status') }}</div>
							<div class="text-sm font-medium text-ink-gray-9">
								{{ memberDetails.data.company.status || '—' }}
							</div>
						</div>
						<div class="bg-surface-gray-1 rounded-md p-3">
							<div class="text-xs text-ink-gray-5 mb-1">{{ __('Member Status') }}</div>
							<div class="text-sm font-medium text-ink-gray-9">
								{{ memberDetails.data.company.member_status || '—' }}
							</div>
						</div>
					</div>
					<Button variant="outline" theme="red" @click="removeFromCompany()">
						{{ __('Remove from Company') }}
					</Button>
				</div>
				<div v-else class="flex items-end gap-3">
					<FormControl
						v-model="companyLink"
						:label="__('Company Account Link')"
						type="text"
						:placeholder="__('Company name or ID')"
						class="w-64"
					/>
					<Button variant="solid" @click="assignCompany()">
						{{ __('Assign') }}
					</Button>
				</div>
			</div>

			<!-- Enrollments -->
			<div>
				<h2 class="mb-3 text-lg font-semibold text-ink-gray-9">
					{{ __('Enrollments') }}
				</h2>
				<div
					v-if="!memberDetails.data.enrollments?.length"
					class="text-sm text-ink-gray-5"
				>
					{{ __('No enrollments found.') }}
				</div>
				<div v-else class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="text-left text-ink-gray-5 border-b">
								<th class="pb-2 pr-4 font-medium">{{ __('Course') }}</th>
								<th class="pb-2 pr-4 font-medium">{{ __('Date') }}</th>
								<th class="pb-2 font-medium">{{ __('Credit Source') }}</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="enrollment in memberDetails.data.enrollments"
								:key="enrollment.name"
								class="border-b last:border-0"
							>
								<td class="py-2 pr-4 text-ink-gray-9">
									{{ enrollment.course_title || enrollment.course }}
								</td>
								<td class="py-2 pr-4 text-ink-gray-6">
									{{ enrollment.creation?.split(' ')[0] || '—' }}
								</td>
								<td class="py-2">
									<Badge
										v-if="enrollment.credit_source"
										:label="enrollment.credit_source"
										variant="subtle"
										size="sm"
									/>
									<span v-else class="text-ink-gray-4">—</span>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</div>

		<!-- Credit Adjustment Dialog -->
		<Dialog
			v-model="showCreditDialog"
			:options="{
				title: __('Adjust Credits'),
				actions: [
					{
						label: __('Apply'),
						variant: 'solid',
						onClick: submitCreditAdjustment,
					},
				],
			}"
		>
			<template #body-content>
				<div class="space-y-4">
					<FormControl
						v-model="creditHours"
						:label="__('Hours (use negative to deduct)')"
						type="number"
						:placeholder="__('e.g. 2 or -1')"
					/>
					<FormControl
						v-model="creditReason"
						:label="__('Reason')"
						type="text"
						:placeholder="__('Reason for adjustment')"
					/>
				</div>
			</template>
		</Dialog>
	</div>
</template>
<script setup>
import { Badge, Button, Dialog, FormControl, call, createResource, toast } from 'frappe-ui'
import { ref, watch, computed } from 'vue'
import Link from '@/components/Controls/Link.vue'

const props = defineProps({
	profile: {
		type: Object,
		required: true,
	},
})

const showCreditDialog = ref(false)
const creditHours = ref(0)
const creditReason = ref('')
const companyLink = ref('')

const memberDetails = createResource({
	url: 'lms.lms.ceu_admin.get_member_admin_details',
	makeParams(values) {
		return {
			user: values.user,
		}
	},
})

watch(
	() => props.profile,
	(newValue) => {
		if (newValue.data?.name) {
			memberDetails.reload({ user: newValue.data.name })
		}
	},
	{ immediate: true }
)

const accountTypeLabel = computed(() => {
	const map = {
		professional: 'Professional',
		company: 'Company',
		one_off: 'One-Off',
	}
	return map[memberDetails.data?.user_type] || memberDetails.data?.user_type || '—'
})

const accountTypeTheme = computed(() => {
	const map = {
		professional: 'blue',
		company: 'purple',
		one_off: 'gray',
	}
	return map[memberDetails.data?.user_type] || 'gray'
})

const submitCreditAdjustment = async () => {
	try {
		await call('lms.lms.ceu_admin.admin_adjust_credits', {
			user: props.profile.data?.name,
			hours: creditHours.value,
			reason: creditReason.value,
		})
		toast.success(__('Credits adjusted successfully'))
		showCreditDialog.value = false
		creditHours.value = 0
		creditReason.value = ''
		memberDetails.reload({ user: props.profile.data?.name })
	} catch (e) {
		toast.error(e.messages?.[0] || __('Failed to adjust credits'))
	}
}

const cancelSubscription = async () => {
	if (!confirm(__('Are you sure you want to cancel this subscription?'))) return
	try {
		await call('lms.lms.ceu_admin.cancel_subscription', {
			user: props.profile.data?.name,
		})
		toast.success(__('Subscription cancelled'))
		memberDetails.reload({ user: props.profile.data?.name })
	} catch (e) {
		toast.error(e.messages?.[0] || __('Failed to cancel subscription'))
	}
}

const openStripe = () => {
	const customerId = memberDetails.data?.membership?.stripe_customer_id
	if (customerId) {
		window.open(`https://dashboard.stripe.com/customers/${customerId}`, '_blank')
	}
}

const removeFromCompany = async () => {
	if (!confirm(__('Remove this user from their company?'))) return
	try {
		await call('lms.lms.ceu_admin.remove_from_company', {
			user: props.profile.data?.name,
		})
		toast.success(__('User removed from company'))
		memberDetails.reload({ user: props.profile.data?.name })
	} catch (e) {
		toast.error(e.messages?.[0] || __('Failed to remove user from company'))
	}
}

const assignCompany = async () => {
	if (!companyLink.value) {
		toast.error(__('Enter a company name or ID'))
		return
	}
	try {
		await call('lms.lms.ceu_admin.assign_company', {
			user: props.profile.data?.name,
			company: companyLink.value,
		})
		toast.success(__('Company assigned'))
		companyLink.value = ''
		memberDetails.reload({ user: props.profile.data?.name })
	} catch (e) {
		toast.error(e.messages?.[0] || __('Failed to assign company'))
	}
}
</script>
