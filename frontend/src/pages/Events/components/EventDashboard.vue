<template>
	<div class="h-[88vh]">
		<div class="grid grid-cols-1 lg:grid-cols-[2fr,1fr] gap-5">
			<div class="p-5">
				<div
					v-if="batch.data?.zoom_link"
					class="mb-8 flex items-center justify-between gap-4 rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-4"
				>
					<div>
						<div class="text-base font-semibold text-ink-gray-9">
							{{ __('Live Webinar') }}
						</div>
						<div class="text-sm text-ink-gray-7">
							<template v-if="batch.data.webinar_window_open">
								{{ __('The webinar is open — click to join now.') }}
							</template>
							<template v-else-if="webinarStartsAt">
								{{ __('Webinar starts on') }} {{ webinarStartsAt }}
							</template>
							<template v-else>
								{{ __('The webinar has ended.') }}
							</template>
						</div>
					</div>
					<a
						v-if="batch.data.webinar_window_open"
						:href="batch.data.zoom_link"
						target="_blank"
						rel="noopener noreferrer"
					>
						<Button variant="solid">
							<template #prefix>
								<Video class="size-4 stroke-1.5" />
							</template>
							{{ __('Join Webinar') }}
						</Button>
					</a>
					<Badge
						v-else-if="webinarStartsAt"
						theme="gray"
						size="lg"
					>
						<template #prefix>
							<Clock class="size-4 stroke-1.5" />
						</template>
						{{ __('Not started') }}
					</Badge>
				</div>
				<div class="mb-8 space-y-2">
					<div class="text-lg text-ink-gray-9 font-semibold">
						{{ __('Curriculum') }}
					</div>
					<div class="text-ink-gray-7">
						{{
							__(
								"As a part of this event's curriculum you will have to complete the following courses and assessments."
							)
						}}
					</div>
				</div>
				<div class="space-y-10">
					<div>
						<div class="text-ink-gray-9 font-semibold mb-4">
							{{ __('Courses') }}
						</div>
						<ListView
							v-if="batch.data?.courses?.length"
							:columns="courseColumns"
							:rows="batch.data?.courses"
							row-key="name"
							class="border rounded-lg"
							:options="{
								showTooltip: false,
								selectable: user.data?.is_student ? false : true,
								getRowRoute: (row) => ({
									name: 'CourseDetail',
									params: { courseName: row.course },
								}),
							}"
						>
							<ListHeader
								class="mb-2 grid items-center space-x-4 rounded-none rounded-t bg-surface-gray-2 p-2"
							>
							</ListHeader>
							<ListRows>
								<ListRow
									:row="row"
									v-for="row in batch.data?.courses"
									class="!rounded-none text-sm"
								>
									<template #default="{ column, item }">
										<ListRowItem :item="row[column.key]" :align="column.align">
											<div v-if="column.key === 'progress'">
												{{ getProgress(row.course) }}%
											</div>
											<div v-else>
												{{ row[column.key] }}
											</div>
										</ListRowItem>
									</template>
								</ListRow>
							</ListRows>
						</ListView>
						<div v-else class="text-ink-gray-7">
							{{ __('No courses added to this event') }}
						</div>
					</div>
					</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import { computed, inject } from 'vue'
import {
	Badge,
	Button,
	createListResource,
	ListView,
	ListHeader,
	ListRows,
	ListRow,
	ListRowItem,
} from 'frappe-ui'
import { Clock, Video } from 'lucide-vue-next'
import { formatTime } from '@/utils'

const user = inject('$user')

const props = defineProps({
	batch: {
		type: Object,
		default: null,
	},
	isStudent: {
		type: Boolean,
		default: false,
	},
})

const progressList = createListResource({
	doctype: 'LMS Enrollment',
	filters: {
		member: user.data?.name,
		course: ['in', props.batch.data?.courses?.map((c) => c.course)],
	},
	fields: ['course', 'progress', 'name'],
	auto: true,
})

const webinarStartsAt = computed(() => {
	const data = props.batch.data
	if (!data) return null
	const days = data.event_days || []
	const now = new Date()
	const upcoming = days
		.map((d) => ({ ...d, dt: new Date(`${d.date}T${d.start_time}`) }))
		.filter((d) => !isNaN(d.dt) && d.dt > now)
		.sort((a, b) => a.dt - b.dt)[0]
	const next = upcoming || (data.start_date && data.start_time
		? { date: data.start_date, start_time: data.start_time, dt: new Date(`${data.start_date}T${data.start_time}`) }
		: null)
	if (!next || isNaN(next.dt) || next.dt <= now) return null
	return `${next.date} ${__('at')} ${formatTime(next.start_time)}`
})

const getProgress = (course) => {
	const progress = progressList.data?.find((p) => p.course === course)
	return progress ? Math.round(progress.progress) : 0
}

const courseColumns = [
	{
		key: 'title',
		label: __('Course'),
	},
	{
		key: 'progress',
		label: __('Progress'),
		align: 'right',
	},
]
</script>
