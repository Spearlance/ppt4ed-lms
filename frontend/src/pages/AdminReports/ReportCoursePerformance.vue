<template>
	<div class="p-5">
		<div v-if="performance.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Course') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Enrolled') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Completed') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Completion Rate') }}</th>
						<th class="pb-2 font-medium text-right">{{ __('Avg Progress') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in performance.data"
						:key="row.course"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 font-medium text-ink-gray-9">{{ row.course_title }}</td>
						<td class="py-3 pr-4 text-right text-ink-gray-7">{{ row.total_enrolled }}</td>
						<td class="py-3 pr-4 text-right text-ink-gray-7">{{ row.completed }}</td>
						<td class="py-3 pr-4 text-right font-mono"
							:class="row.completion_rate >= 70 ? 'text-green-600' : 'text-ink-gray-7'"
						>
							{{ row.completion_rate }}%
						</td>
						<td class="py-3 text-right font-mono text-ink-gray-7">
							{{ row.avg_progress }}%
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="performance.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No course data yet.') }}
		</div>
	</div>
</template>

<script setup>
import { createResource } from 'frappe-ui'

const performance = createResource({
	url: 'lms.lms.ceu_reports.get_course_performance_report',
	cache: ['report-course-performance'],
	auto: true,
})
</script>
