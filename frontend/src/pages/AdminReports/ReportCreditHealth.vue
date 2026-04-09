<template>
	<div class="p-5">
		<div v-if="health.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Member') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Plan') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Balance') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Expiry') }}</th>
						<th class="pb-2 font-medium">{{ __('Flags') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in health.data"
						:key="row.membership"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 font-medium text-ink-gray-9">{{ row.member_name }}</td>
						<td class="py-3 pr-4 text-ink-gray-7">{{ row.plan }}</td>
						<td class="py-3 pr-4 text-right font-mono"
							:class="row.credit_balance <= 0 ? 'text-red-600' : 'text-orange-600'"
						>
							{{ row.credit_balance }}
						</td>
						<td class="py-3 pr-4 text-ink-gray-5">
							{{ row.expiry_date || '—' }}
						</td>
						<td class="py-3">
							<Badge theme="red">{{ row.flags }}</Badge>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="health.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-green-600">
			{{ __('All memberships healthy — no low balances or upcoming expirations.') }}
		</div>
	</div>
</template>

<script setup>
import { Badge, createResource } from 'frappe-ui'

const health = createResource({
	url: 'lms.lms.ceu_reports.get_credit_health_report',
	cache: ['report-credit-health'],
	auto: true,
})
</script>
