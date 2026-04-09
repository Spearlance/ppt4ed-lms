<template>
	<div class="p-5">
		<div v-if="members.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Type') }}</th>
						<th class="pb-2 pr-4 font-medium">{{ __('Status') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Count') }}</th>
						<th class="pb-2 font-medium text-right">{{ __('Total Credits') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="(row, idx) in members.data"
						:key="idx"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 font-medium text-ink-gray-9">{{ row.membership_type }}</td>
						<td class="py-3 pr-4">
							<Badge :theme="row.status === 'Active' ? 'green' : 'gray'">
								{{ row.status }}
							</Badge>
						</td>
						<td class="py-3 pr-4 text-right text-ink-gray-7">{{ row.count }}</td>
						<td class="py-3 text-right font-mono text-ink-gray-9">{{ row.total_credits }}</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="members.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No membership data yet.') }}
		</div>
	</div>
</template>

<script setup>
import { Badge, createResource } from 'frappe-ui'

const members = createResource({
	url: 'lms.lms.ceu_reports.get_members_report',
	cache: ['report-members'],
	auto: true,
})
</script>
