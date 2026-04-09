<template>
	<div class="p-5">
		<div v-if="usage.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Member') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Plan') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Status') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Allocated') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Used') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Balance') }}</th>
						<th class="pb-2 font-medium text-right">{{ __('Utilization') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in usage.data"
						:key="row.membership"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 font-medium text-ink-gray-9">{{ row.member_name }}</td>
						<td class="py-3 pr-4 text-ink-gray-7">{{ row.plan }}</td>
						<td class="py-3 pr-4">
							<Badge :theme="row.status === 'Active' ? 'green' : 'gray'">
								{{ row.status }}
							</Badge>
						</td>
						<td class="py-3 pr-4 text-right font-mono text-ink-gray-7">{{ row.total_allocated }}</td>
						<td class="py-3 pr-4 text-right font-mono text-ink-gray-7">{{ row.total_used }}</td>
						<td class="py-3 pr-4 text-right font-mono text-ink-gray-9">{{ row.credit_balance }}</td>
						<td class="py-3 text-right font-mono"
							:class="row.utilization_pct > 80 ? 'text-green-600' : 'text-ink-gray-7'"
						>
							{{ row.utilization_pct }}%
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="usage.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No usage data yet.') }}
		</div>
	</div>
</template>

<script setup>
import { Badge, createResource } from 'frappe-ui'

const usage = createResource({
	url: 'lms.lms.ceu_reports.get_member_usage_report',
	cache: ['report-usage'],
	auto: true,
})
</script>
