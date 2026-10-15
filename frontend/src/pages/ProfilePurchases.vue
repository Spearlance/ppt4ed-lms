<template>
	<div class="mt-7 mb-10" data-testid="profile-purchases">
		<h2 class="mb-3 text-lg font-semibold text-ink-gray-9">
			{{ __('Purchases') }}
		</h2>
		<div v-if="purchases.loading" class="text-sm text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else-if="purchases.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="text-left text-ink-gray-5 border-b">
						<th class="pb-2 pr-4 font-medium">{{ __('Date') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Item') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Amount') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Status') }}</th>
						<th class="pb-2 font-medium text-right">{{ __('Receipt') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in purchases.data"
						:key="row.name"
						class="border-b last:border-b-0 text-ink-gray-9"
					>
						<td class="py-2.5 pr-4 whitespace-nowrap">
							{{ dayjs(row.transaction_date).format('DD MMM YYYY') }}
						</td>
						<td class="py-2.5 pr-4">
							<router-link
								v-if="itemRoute(row)"
								:to="itemRoute(row)"
								class="hover:underline"
							>
								{{ row.title }}
							</router-link>
							<span v-else>{{ row.title }}</span>
							<div class="text-xs text-ink-gray-5">
								{{ typeLabel(row.transaction_type) }}
							</div>
						</td>
						<td class="py-2.5 pr-4 whitespace-nowrap">
							<span>{{ row.amount_display }}</span>
							<div
								v-if="row.refunded_amount > 0"
								class="text-xs text-ink-gray-5"
							>
								{{ __('Net') }} {{ row.net_display }}
							</div>
						</td>
						<td class="py-2.5 pr-4 whitespace-nowrap">
							<Badge :theme="statusTheme(row.status)" variant="subtle">
								{{ __(row.status || 'Succeeded') }}
							</Badge>
						</td>
						<td class="py-2.5 text-right whitespace-nowrap">
							<a
								v-if="row.receipt_url"
								:href="row.receipt_url"
								target="_blank"
								rel="noopener"
								:aria-label="`${__('View receipt')} ${row.title}`"
								class="inline-flex items-center gap-1 text-ink-gray-7 hover:text-ink-gray-9 hover:underline"
							>
								<FileText class="size-4 stroke-1.5" />
								{{ __('View receipt') }}
							</a>
							<span v-else class="text-xs text-ink-gray-5">
								{{ __('Not available') }}
							</span>
						</td>
					</tr>
				</tbody>
			</table>
			<p class="mt-3 text-xs text-ink-gray-5">
				{{
					__(
						'Receipts open on Stripe, our payment processor. Use the print or download option on that page to save a copy.'
					)
				}}
			</p>
		</div>
		<div v-else class="text-sm italic text-ink-gray-5">
			{{ __('No purchases yet.') }}
		</div>
	</div>
</template>
<script setup>
import { Badge, createResource } from 'frappe-ui'
import { FileText } from 'lucide-vue-next'
import { inject } from 'vue'

const dayjs = inject('$dayjs')
const props = defineProps({
	profile: {
		type: Object,
		required: true,
	},
})

const purchases = createResource({
	url: 'lms.lms.ceu_transactions.get_member_purchases',
	params: { member: props.profile.data?.name },
	cache: ['purchases', props.profile.data?.name],
	auto: Boolean(props.profile.data?.name),
})

const typeLabel = (type) => {
	return (
		{
			Course: __('Course'),
			Event: __('Event'),
			Membership: __('Membership'),
			Other: __('Payment'),
		}[type] || type
	)
}

const statusTheme = (status) => {
	if (status === 'Refunded') return 'gray'
	if (status === 'Partially Refunded') return 'orange'
	return 'green'
}

const itemRoute = (row) => {
	if (!row.item) return null
	if (row.item_type === 'LMS Course') {
		return { name: 'CourseDetail', params: { courseName: row.item } }
	}
	if (row.item_type === 'LMS Event') {
		return { name: 'EventDetail', params: { eventName: row.item } }
	}
	return null
}
</script>
