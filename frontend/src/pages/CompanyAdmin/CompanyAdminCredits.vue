<template>
	<div class="p-5">
		<div class="flex items-center justify-between mb-4">
			<h3 class="text-sm font-medium text-ink-gray-7">{{ __('Credit History') }}</h3>
			<Button variant="outline" @click="showAdjustDialog = true">
				{{ __('Adjust Credits') }}
			</Button>
		</div>

		<div v-if="credits.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Date') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Type') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('User') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Course') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Reason') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Hours') }}</th>
						<th class="pb-2 font-medium text-right">{{ __('Balance') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="entry in credits.data"
						:key="entry.name"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 text-ink-gray-5">
							{{ dayjs(entry.timestamp).format('MMM D, YYYY h:mm A') }}
						</td>
						<td class="py-3 pr-4">
							<Badge :theme="entry.transaction_type === 'Allocation' ? 'green' : 'blue'">
								{{ entry.transaction_type }}
							</Badge>
						</td>
						<td class="py-3 pr-4 text-ink-gray-7">
							{{ entry.user_name }}
						</td>
						<td class="py-3 pr-4 text-ink-gray-7">
							{{ entry.course || '—' }}
						</td>
						<td class="py-3 pr-4 text-ink-gray-7">
							{{ entry.reason || '—' }}
						</td>
						<td
							class="py-3 pr-4 text-right font-mono"
							:class="entry.hours > 0 ? 'text-green-600' : 'text-ink-gray-7'"
						>
							{{ entry.hours > 0 ? '+' : '' }}{{ entry.hours }}
						</td>
						<td class="py-3 text-right font-mono text-ink-gray-9">
							{{ entry.balance_after }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="credits.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No credit activity yet.') }}
		</div>

		<!-- Adjust Credits Dialog -->
		<Dialog v-model="showAdjustDialog" :options="{ title: __('Adjust Credits') }">
			<template #body-content>
				<div class="space-y-4 mt-2">
					<div>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Hours (positive to add, negative to deduct)') }}
						</label>
						<FormControl
							v-model="adjustForm.hours"
							type="number"
							:placeholder="__('e.g. 10 or -5')"
						/>
					</div>
					<div>
						<label class="block text-sm font-medium text-ink-gray-7 mb-1">
							{{ __('Reason') }}
						</label>
						<FormControl
							v-model="adjustForm.reason"
							type="textarea"
							:placeholder="__('Enter reason for adjustment...')"
						/>
					</div>
				</div>
			</template>
			<template #actions>
				<Button
					variant="solid"
					:loading="adjustResource.loading"
					@click="submitAdjustment"
				>
					{{ __('Apply Adjustment') }}
				</Button>
				<Button variant="outline" @click="showAdjustDialog = false">
					{{ __('Cancel') }}
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { ref } from 'vue'
import { Badge, Button, Dialog, FormControl, createResource, toast } from 'frappe-ui'
import dayjs from 'dayjs'

const props = defineProps({
	company: {
		type: Object,
		required: true,
	},
})

const showAdjustDialog = ref(false)
const adjustForm = ref({ hours: 0, reason: '' })

const credits = createResource({
	url: 'lms.lms.ceu_admin.get_company_credit_history',
	params: () => ({ company: props.company.data?.name }),
	cache: () => [`company-admin-credits-${props.company.data?.name}`],
	auto: true,
})

const adjustResource = createResource({
	url: 'lms.lms.ceu_admin.admin_adjust_credits',
	onSuccess() {
		toast({ title: __('Credits adjusted'), icon: 'check', iconClasses: 'text-green-500' })
		showAdjustDialog.value = false
		adjustForm.value = { hours: 0, reason: '' }
		credits.reload()
		props.company.reload()
	},
	onError(err) {
		toast({ title: __('Error'), text: err.message, icon: 'x', iconClasses: 'text-red-500' })
	},
})

const submitAdjustment = () => {
	if (!adjustForm.value.hours) return
	adjustResource.submit({
		company: props.company.data.name,
		hours: adjustForm.value.hours,
		reason: adjustForm.value.reason,
	})
}
</script>
