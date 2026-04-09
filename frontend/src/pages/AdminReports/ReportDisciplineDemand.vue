<template>
	<div class="p-5">
		<div v-if="demand.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Discipline') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Enrollments') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Courses') }}</th>
						<th class="pb-2 font-medium text-right">{{ __('Unique Members') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in demand.data"
						:key="row.discipline"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 font-medium text-ink-gray-9">{{ row.discipline }}</td>
						<td class="py-3 pr-4 text-right text-ink-gray-7">{{ row.enrollment_count }}</td>
						<td class="py-3 pr-4 text-right text-ink-gray-7">{{ row.course_count }}</td>
						<td class="py-3 text-right text-ink-gray-7">{{ row.unique_members }}</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="demand.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No discipline data yet.') }}
		</div>
	</div>
</template>

<script setup>
import { createResource } from 'frappe-ui'

const demand = createResource({
	url: 'lms.lms.ceu_reports.get_discipline_demand_report',
	cache: ['report-discipline-demand'],
	auto: true,
})
</script>
