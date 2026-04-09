<template>
	<div class="p-5">
		<div v-if="revenue.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Period') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Transactions') }}</th>
						<th class="pb-2 font-medium text-right">{{ __('Total Hours') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in revenue.data"
						:key="row.period"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 font-medium text-ink-gray-9">{{ row.period }}</td>
						<td class="py-3 pr-4 text-right text-ink-gray-7">{{ row.transaction_count }}</td>
						<td class="py-3 text-right font-mono text-ink-gray-9">{{ row.total_hours }}</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="revenue.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No revenue data yet.') }}
		</div>
	</div>
</template>

<script setup>
import { createResource } from 'frappe-ui'

const revenue = createResource({
	url: 'lms.lms.ceu_reports.get_revenue_report',
	params: { period: 'monthly' },
	cache: ['report-revenue'],
	auto: true,
})
</script>
