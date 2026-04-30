<template>
	<div class="">
		<div class="grid grid-cols-1 lg:grid-cols-[3fr,2fr]">
			<div v-if="batchDetail.doc" class="py-5 lg:h-[88vh] lg:overflow-y-auto">
				<div class="px-5 pb-5 space-y-5 border-b mb-5">
					<div class="text-lg text-ink-gray-9 font-semibold mb-4">
						{{ __('Details') }}
					</div>

					<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
						<div class="space-y-5">
							<Switch
								size="sm"
								v-model="batchDetail.doc.published"
								:label="__('Published')"
								:description="__('Make the event visible to all users.')"
							/>
							<FormControl
								v-model="batchDetail.doc.title"
								:label="__('Title')"
								:required="true"
								class="w-full"
							/>
							<FormControl
								v-model="batchDetail.doc.start_date"
								:label="__('Event Start Date')"
								type="date"
								class="mb-4"
								:required="true"
							/>
							<FormControl
								v-model="batchDetail.doc.end_date"
								:label="__('Event End Date')"
								type="date"
								class="mb-4"
								:required="true"
							/>
							<FormControl
								v-model="batchDetail.doc.seat_count"
								:label="__('Seat Count')"
								type="number"
								class="mb-4"
								:placeholder="__('Number of seats available')"
							/>
							<FormControl
								v-model="batchDetail.doc.credit_hours"
								:label="__('CEU Credit Hours')"
								type="number"
								class="mb-4"
								:placeholder="__('e.g. 2.0')"
							/>
						</div>
						<div class="space-y-5">
							<Switch
								size="sm"
								v-model="batchDetail.doc.allow_self_enrollment"
								:label="__('Allow Self Enrollment')"
								:description="
									__('Allow users to enroll in this event on their own.')
								"
							/>
							<FormControl
								v-model="batchDetail.doc.start_time"
								:label="__('Session Start Time')"
								type="time"
								class="mb-4"
								:required="true"
							/>
							<FormControl
								v-model="batchDetail.doc.end_time"
								:label="__('Session End Time')"
								type="time"
								class="mb-4"
								:required="true"
							/>
							<FormControl
								v-model="batchDetail.doc.timezone"
								:label="__('Timezone')"
								type="text"
								:placeholder="__('Example: IST (+5:30)')"
								class="mb-4"
								:required="true"
							/>

							<MultiSelect
								v-model="categories"
								doctype="LMS Category"
								:label="__('Categories')"
							/>
						</div>
					</div>
				</div>

				<div class="px-5 pb-5 space-y-5 border-b mb-5">
					<div class="flex items-center justify-between mb-2">
						<div class="text-lg text-ink-gray-9 font-semibold">
							{{ __('Per-day Schedule') }}
						</div>
						<Button @click="addEventDay">
							<template #prefix>
								<Plus class="w-4 h-4 stroke-1.5" />
							</template>
							{{ __('Add Day') }}
						</Button>
					</div>
					<div class="text-sm text-ink-gray-6 -mt-1 mb-2">
						{{
							__(
								'One row per day the event runs. The Start/End Date and Time fields above stay as the overall event window.'
							)
						}}
					</div>
					<div
						v-for="(day, idx) in eventDays"
						:key="idx"
						class="grid grid-cols-[1fr,1fr,1fr,auto] gap-3 items-end"
					>
						<FormControl
							v-model="day.date"
							:label="idx === 0 ? __('Date') : ''"
							type="date"
							:required="true"
						/>
						<FormControl
							v-model="day.start_time"
							:label="idx === 0 ? __('Start Time') : ''"
							type="time"
							:required="true"
						/>
						<FormControl
							v-model="day.end_time"
							:label="idx === 0 ? __('End Time') : ''"
							type="time"
							:required="true"
						/>
						<Button
							variant="ghost"
							theme="red"
							:disabled="eventDays.length <= 1"
							@click="removeEventDay(idx)"
						>
							<X class="w-4 h-4 stroke-1.5" />
						</Button>
					</div>
				</div>

				<div class="px-5 pb-5 space-y-5 border-b mb-5">
					<div class="text-lg text-ink-gray-9 font-semibold mb-4">
						{{ __('Certification') }}
					</div>
					<div class="grid grid-cols-1 md:grid-cols-2 gap-5 items-start">
						<div class="flex flex-col space-y-5">
							<Switch
								size="sm"
								v-model="batchDetail.doc.evaluation"
								:label="__('Evaluation')"
								:description="__('Enable evaluations for event participants.')"
							/>
							<FormControl
								v-if="batchDetail.doc.evaluation"
								v-model="batchDetail.doc.evaluation_end_date"
								:label="__('Evaluation End Date')"
								type="date"
								class="mb-4"
							/>
						</div>
						<div>
							<Switch
								size="sm"
								v-model="batchDetail.doc.certification"
								:label="__('Certification')"
								:description="__('Issue certificates to event participants.')"
							/>
						</div>
					</div>
				</div>

				<div class="px-5 pb-5 space-y-5 border-b mb-5">
					<div class="grid grid-cols-2 gap-5">
						<MultiSelect
							v-model="instructors"
							doctype="User"
							:label="__('Instructors')"
							:required="true"
							:onCreate="() => (showMemberModal = true)"
							url="lms.lms.api.search_users_by_role"
							:searchParams="{ roles: JSON.stringify(['Moderator', 'LMS Student']) }"
						/>
						<FormControl
							v-model="batchDetail.doc.description"
							:label="__('Short Description')"
							type="textarea"
							:rows="4"
							:placeholder="__('Short description of the event')"
							:required="true"
						/>
					</div>
					<div>
						<label class="block text-sm text-ink-gray-5 mb-2">
							{{ __('Event Details') }}
							<span class="text-ink-red-3">*</span>
						</label>
						<TextEditor
							:content="batchDetail.doc.event_details"
							@change="(val) => (batchDetail.doc.event_details = val)"
							:editable="true"
							:fixedMenu="true"
							editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem] max-h-[16rem] overflow-y-scroll mb-4"
						/>
					</div>
				</div>

				<div class="px-5 pb-5 space-y-5 border-b mb-5">
					<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
						<div class="space-y-5">
							<FormControl
								v-model="batchDetail.doc.event_type"
								type="select"
								:options="eventTypeOptions"
								:label="__('Event Type')"
								class="mb-4"
							/>
							<FormControl
								v-if="batchDetail.doc.event_type === 'In-Person'"
								v-model="batchDetail.doc.venue"
								:label="__('Venue / Location')"
								type="textarea"
								:rows="2"
								class="mb-4"
								:placeholder="__('Address or venue name')"
							/>
							<FormControl
								v-model="batchDetail.doc.medium"
								type="select"
								:options="mediumOptions"
								:label="__('Medium')"
								class="mb-4"
							/>
							<Link
								ref="emailTemplateLinkRef"
								doctype="Email Template"
								:label="__('Enrollment Confirmation Email Template')"
								v-model="batchDetail.doc.confirmation_email_template"
								:onCreate="
									(value, close) => {
										if (close) close()
										showEmailTemplateModal = true
									}
								"
							/>
						</div>
						<Uploader
							v-model="batchDetail.doc.video_link"
							:label="__('Preview Video')"
							type="video"
							:required="false"
						/>
					</div>
				</div>

				<div class="px-5 pb-5 space-y-5 border-b mb-5">
					<div class="text-lg text-ink-gray-9 font-semibold mb-4">
						{{ __('Conferencing') }}
					</div>
					<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
						<FormControl
							v-model="batchDetail.doc.conferencing_provider"
							type="select"
							:options="conferencingOptions"
							:label="__('Conferencing Provider')"
						/>
						<Link
							v-if="batchDetail.doc.conferencing_provider === 'Zoom'"
							doctype="LMS Zoom Settings"
							:label="__('Zoom Account')"
							v-model="batchDetail.doc.zoom_account"
							:onCreate="
								(value, close) => {
									openSettings('Zoom Accounts', close)
								}
							"
						/>
						<Link
							v-if="batchDetail.doc.conferencing_provider === 'Google Meet'"
							doctype="LMS Google Meet Settings"
							:label="__('Google Meet Account')"
							v-model="batchDetail.doc.google_meet_account"
							:onCreate="
								(value, close) => {
									openSettings('Google Meet Accounts', close)
								}
							"
						/>
					</div>
				</div>

				<div class="px-5 pb-5 space-y-5 border-b mb-5">
					<div class="text-lg text-ink-gray-9 font-semibold">
						{{ __('Pricing') }}
					</div>
					<Switch
						size="sm"
						v-model="batchDetail.doc.paid_event"
						:label="__('Paid Event')"
						:description="__('Charge a fee for event enrollment.')"
					/>
					<div
						v-if="batchDetail.doc.paid_event"
						class="grid grid-cols-1 md:grid-cols-2 gap-5"
					>
						<FormControl
							v-model="batchDetail.doc.amount"
							:label="__('Amount')"
							type="number"
						/>
						<Link
							doctype="Currency"
							v-model="batchDetail.doc.currency"
							:filters="{ enabled: 1 }"
							:label="__('Currency')"
						/>
						<FormControl
							v-model="batchDetail.doc.amount_usd"
							:label="__('Amount (USD)')"
							type="number"
							:placeholder="__('Used for Stripe checkout')"
						/>
					</div>
					<div
						v-if="batchDetail.doc.paid_event"
						class="border-t pt-4 mt-2"
					>
						<div class="text-sm font-semibold text-ink-gray-9 mb-1">
							{{ __('Early Bird') }}
						</div>
						<div class="text-xs text-ink-gray-6 mb-3">
							{{
								__(
									'Optional discount applied automatically when the event is purchased on or before the deadline. Leave blank to disable.'
								)
							}}
						</div>
						<div class="grid grid-cols-1 md:grid-cols-3 gap-5">
							<FormControl
								v-model="batchDetail.doc.early_bird_amount"
								:label="__('Early Bird Amount')"
								type="number"
							/>
							<FormControl
								v-model="batchDetail.doc.early_bird_amount_usd"
								:label="__('Early Bird Amount (USD)')"
								type="number"
							/>
							<FormControl
								v-model="batchDetail.doc.early_bird_deadline"
								:label="__('Deadline')"
								type="date"
							/>
						</div>
					</div>
				</div>

				<div class="px-5 pb-5 space-y-5">
					<div class="text-lg text-ink-gray-9 font-semibold">
						{{ __('Meta Tags') }}
					</div>
					<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
						<FormControl
							v-model="meta.description"
							:label="__('Meta Description')"
							type="textarea"
							:rows="4"
						/>
						<FormControl
							v-model="meta.keywords"
							:label="__('Meta Keywords')"
							type="textarea"
							:rows="4"
							:placeholder="__('Comma separated keywords')"
						/>
						<Uploader
							v-model="batchDetail.doc.meta_image"
							:label="__('Meta Image')"
							type="image"
							:required="false"
						/>
					</div>
				</div>
			</div>
		</div>
	</div>
	<NewMemberModal
		v-model="showMemberModal"
		:defaultRoles="['moderator']"
		@created="onInstructorCreated"
	/>
	<EmailTemplateModal
		v-model="showEmailTemplateModal"
		v-model:emailTemplates="emailTemplates"
		templateID="new"
		@created="onEmailTemplateCreated"
	/>
</template>
<script setup>
import {
	computed,
	getCurrentInstance,
	inject,
	onMounted,
	onBeforeUnmount,
	reactive,
	ref,
	toRaw,
	watch,
	nextTick,
} from 'vue'
import {
	Button,
	FormControl,
	Switch,
	TextEditor,
	createDocumentResource,
	toast,
	call,
	createListResource,
} from 'frappe-ui'
import { Plus, X } from 'lucide-vue-next'
import {
	getMetaInfo,
	openSettings,
	sanitizeHTML,
	updateMetaInfo,
} from '@/utils'
import { useRouter } from 'vue-router'
import { useTelemetry } from 'frappe-ui/frappe'
import Uploader from '@/components/Controls/Uploader.vue'
import MultiSelect from '@/components/Controls/MultiSelect.vue'
import Link from '@/components/Controls/Link.vue'
import NewMemberModal from '@/components/Modals/NewMemberModal.vue'
import EmailTemplateModal from '@/components/Modals/EmailTemplateModal.vue'

const router = useRouter()
const user = inject('$user')
const instructors = ref([])
const categories = ref([])
const eventDays = ref([])
const app = getCurrentInstance()
const { capture } = useTelemetry()
const { $dialog } = app.appContext.config.globalProperties
const isDirty = ref(false)
const originalDoc = ref(null)
const showMemberModal = ref(false)
const showEmailTemplateModal = ref(false)
const emailTemplateLinkRef = ref(null)

const emailTemplates = createListResource({
	doctype: 'Email Template',
	fields: ['name', 'subject', 'use_html', 'response', 'response_html'],
	auto: true,
	orderBy: 'modified desc',
	cache: 'email-templates',
})

const onEmailTemplateCreated = (name) => {
	batchDetail.doc.confirmation_email_template = name
	emailTemplateLinkRef.value?.reload()
}

const onInstructorCreated = (user) => {
	instructors.value = [...instructors.value, user.name]
}

const addEventDay = () => {
	const last = eventDays.value[eventDays.value.length - 1]
	eventDays.value.push({
		date: last?.date || batchDetail.doc?.start_date || null,
		start_time: last?.start_time || batchDetail.doc?.start_time || null,
		end_time: last?.end_time || batchDetail.doc?.end_time || null,
	})
}

const removeEventDay = (idx) => {
	if (eventDays.value.length <= 1) return
	eventDays.value.splice(idx, 1)
}

const meta = reactive({
	description: '',
	keywords: '',
})

const props = defineProps({
	batch: {
		type: Object,
		required: true,
	},
})

onMounted(() => {
	if (!user.data) window.location.href = '/login'
	window.addEventListener('keydown', keyboardShortcut)
})

const keyboardShortcut = (e) => {
	if (
		e.key === 's' &&
		(e.ctrlKey || e.metaKey) &&
		!e.target.classList.contains('ProseMirror')
	) {
		submitEvent()
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
})

const batchDetail = createDocumentResource({
	doctype: 'LMS Event',
	name: props.batch.data?.name,
	auto: true,
})

watch(
	() => batchDetail.doc,
	() => {
		if (!batchDetail.doc) return

		if (originalDoc.value) {
			isDirty.value =
				JSON.stringify(batchDetail.doc) !== JSON.stringify(originalDoc.value)
		}

		updateBatchData()
		getMetaInfo('events', batchDetail.doc?.name, meta)
	},
	{ deep: true }
)

const updateBatchData = () => {
	Object.keys(batchDetail.doc).forEach((key) => {
		if (key == 'instructors') {
			instructors.value = []
			batchDetail.doc.instructors.forEach((instructor) => {
				instructors.value.push(instructor.instructor)
			})
		} else if (key == 'categories') {
			categories.value = (batchDetail.doc.categories || []).map(
				(row) => row.category
			)
		} else if (key == 'event_days') {
			eventDays.value = (batchDetail.doc.event_days || []).map((row) => ({
				date: row.date,
				start_time: formatTime(row.start_time),
				end_time: formatTime(row.end_time),
			}))
		} else if (['start_time', 'end_time'].includes(key)) {
			batchDetail.doc[key] = formatTime(batchDetail.doc[key])
		}
	})
	if (!eventDays.value.length) {
		eventDays.value = [
			{
				date: batchDetail.doc.start_date,
				start_time: batchDetail.doc.start_time,
				end_time: batchDetail.doc.end_time,
			},
		]
	}
	let checkboxes = [
		'published',
		'paid_event',
		'allow_self_enrollment',
		'certification',
		'evaluation',
	]
	for (let idx in checkboxes) {
		let key = checkboxes[idx]
		batchDetail.doc[key] = batchDetail.doc[key] ? true : false
	}
	originalDoc.value = structuredClone(toRaw(batchDetail.doc))
}

const formatTime = (timeStr) => {
	if (!timeStr) return timeStr
	let [hours, minutes, seconds] = timeStr.split(':')
	hours = hours.length == 1 ? '0' + hours : hours
	return `${hours}:${minutes}`
}

const validateFields = () => {
	Object.keys(batchDetail.doc).forEach((key) => {
		if (typeof batchDetail.doc[key] === 'string') {
			batchDetail.doc[key] = sanitizeHTML(batchDetail.doc[key])
		}
	})
}

const submitEvent = () => {
	validateFields()
	updateEvent()
}

const updateEvent = () => {
	batchDetail.setValue.submit(
		{
			...batchDetail.doc,
			instructors: instructors.value.map((instructor) => ({
				instructor: instructor,
			})),
			categories: categories.value.map((category) => ({ category })),
			event_days: eventDays.value.map((day) => ({
				date: day.date,
				start_time: day.start_time,
				end_time: day.end_time,
			})),
		},
		{
			onSuccess(data) {
				updateMetaInfo('events', data.name, meta)
				toast.success(__('Event updated successfully'))
				nextTick(() => {
					originalDoc.value = structuredClone(data)
					isDirty.value = false
				})
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
				console.error(err)
			},
		}
	)
}

const deleteEvent = () => {
	$dialog({
		title: __('Confirm your action to delete'),
		message: __(
			'Deleting this event will also delete all its data including enrolled students, linked courses, assessments, feedback and discussions. Are you sure you want to continue?'
		),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick({ close }) {
					trashEvent(close)
					close()
				},
			},
		],
	})
}

const trashEvent = (close) => {
	call('lms.lms.api.delete_event', {
		event: props.batch.data.name,
	}).then(() => {
		toast.success(__('Event deleted successfully'))
		close()
		router.push({
			name: 'Events',
		})
	})
}

const conferencingOptions = computed(() => {
	return [
		{
			label: '',
			value: '',
		},
		{
			label: __('Zoom'),
			value: 'Zoom',
		},
		{
			label: __('Google Meet'),
			value: 'Google Meet',
		},
	]
})

const eventTypeOptions = computed(() => {
	return [
		{
			label: '',
			value: '',
		},
		{
			label: __('Live Webinar'),
			value: 'Live Webinar',
		},
		{
			label: __('In-Person'),
			value: 'In-Person',
		},
	]
})

const mediumOptions = computed(() => {
	return [
		{
			label: __('Online'),
			value: 'Online',
		},
		{
			label: __('Offline'),
			value: 'Offline',
		},
	]
})

defineExpose({
	submitEvent,
	deleteEvent,
	isDirty,
})
</script>
