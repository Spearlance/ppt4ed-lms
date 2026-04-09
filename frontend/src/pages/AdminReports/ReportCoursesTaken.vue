<template>
	<div class="p-5">
		<div v-if="courses.data?.length" class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-5">
						<th class="pb-2 pr-4 font-medium">{{ __('Course') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('Enrollments') }}</th>
						<th class="pb-2 pr-4 font-medium text-right">{{ __('CEU Hours') }}</th>
						<th class="pb-2 font-medium">{{ __('Disciplines') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="row in courses.data"
						:key="row.course"
						class="border-b last:border-0"
					>
						<td class="py-3 pr-4 font-medium text-ink-gray-9">{{ row.course_title }}</td>
						<td class="py-3 pr-4 text-right text-ink-gray-7">{{ row.enrollment_count }}</td>
						<td class="py-3 pr-4 text-right font-mono text-ink-gray-9">{{ row.ceu_hours || '—' }}</td>
						<td class="py-3 text-ink-gray-5">{{ row.disciplines || '—' }}</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-else-if="courses.loading" class="text-center py-10 text-ink-gray-5">
			{{ __('Loading...') }}
		</div>
		<div v-else class="text-center py-10 text-ink-gray-5">
			{{ __('No enrollment data yet.') }}
		</div>
	</div>
</template>

<script setup>
import { createResource } from 'frappe-ui'

const courses = createResource({
	url: 'lms.lms.ceu_reports.get_courses_taken_report',
	cache: ['report-courses-taken'],
	auto: true,
})
</script>
