<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('New Event'),
			size: '3xl',
		}"
	>
		<template #body-content>
			<div class="text-base">
				<div class="grid grid-cols-3 gap-5">
					<FormControl
						v-model="batch.title"
						:label="__('Title')"
						:required="true"
						autocomplete="off"
					/>
					<FormControl
						v-model="batch.start_date"
						:label="__('Start Date')"
						type="date"
						:required="true"
					/>
					<FormControl
						v-model="batch.end_date"
						:label="__('End Date')"
						type="date"
						:required="true"
					/>
					<FormControl
						v-model="batch.start_time"
						:label="__('Start Time')"
						type="time"
						:required="true"
					/>
					<FormControl
						v-model="batch.end_time"
						:label="__('End Time')"
						type="time"
						:required="true"
					/>
					<FormControl
						v-model="batch.timezone"
						:label="__('Timezone')"
						:required="true"
						autocomplete="off"
					/>
					<MultiSelect
						v-model="batch.categories"
						doctype="LMS Category"
						:label="__('Categories')"
					/>
					<FormControl
						v-model="batch.seat_count"
						:label="__('Seat Count')"
						type="number"
						:required="false"
					/>
					<FormControl
						v-model="batch.medium"
						type="select"
						:options="mediumOptions"
						:label="__('Medium')"
						class="mb-4"
					/>
					<FormControl
						v-model="batch.event_type"
						type="select"
						:options="eventTypeOptions"
						:label="__('Event Type')"
					/>
					<FormControl
						v-model="batch.credit_hours"
						:label="__('CEU Credit Hours')"
						type="number"
						:placeholder="__('e.g. 2.0')"
					/>
					<FormControl
						v-if="batch.event_type === 'In-Person'"
						v-model="batch.venue"
						:label="__('Venue / Location')"
						type="textarea"
						:rows="2"
						:placeholder="__('Address or venue name')"
					/>
				</div>

				<div class="space-y-5 border-t mt-5 pt-5">
					<div class="flex items-center justify-between">
						<div>
							<div class="text-sm font-medium text-ink-gray-9">
								{{ __('Paid Event') }}
							</div>
							<div class="text-xs text-ink-gray-6">
								{{ __('Charge a fee for event registration.') }}
							</div>
						</div>
						<Switch size="sm" v-model="batch.paid_event" />
					</div>
					<div
						v-if="batch.paid_event"
						class="grid grid-cols-2 gap-5"
					>
						<FormControl
							v-model="batch.amount"
							:label="__('Amount')"
							type="number"
							:required="true"
						/>
						<Link
							doctype="Currency"
							v-model="batch.currency"
							:filters="{ enabled: 1 }"
							:label="__('Currency')"
							:required="true"
						/>
					</div>
				</div>

				<div class="space-y-5 border-t mt-5 pt-5">
					<div class="grid grid-cols-2 gap-5">
						<FormControl
							v-model="batch.description"
							:label="__('Description')"
							type="textarea"
							:required="true"
							:rows="4"
						/>
						<MultiSelect
							v-model="batch.instructors"
							doctype="User"
							:label="__('Instructors')"
							:required="true"
							:onCreate="() => (showMemberModal = true)"
							url="lms.lms.api.search_users_by_role"
							:searchParams="{ roles: JSON.stringify(['Moderator', 'LMS Student']) }"
						/>
					</div>
					<div class="">
						<div class="mb-1.5 text-sm text-ink-gray-5">
							{{ __('Event Details') }}
							<span class="text-ink-red-3">*</span>
						</div>
						<TextEditor
							:content="batch.event_details"
							@change="(val: string) => (batch.event_details = val)"
							:editable="true"
							:fixedMenu="true"
							editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[10rem] max-h-[14rem] overflow-auto"
						/>
					</div>
				</div>
			</div>
		</template>
		<template #actions="{ close }">
			<div class="text-right">
				<Button variant="solid" @click="saveBatch(close)">
					{{ __('Save') }}
				</Button>
			</div>
		</template>
	</Dialog>
	<NewMemberModal
		v-model="showMemberModal"
		:defaultRoles="[]"
		@created="onInstructorCreated"
	/>
</template>
<script setup lang="ts">
import { Button, Dialog, FormControl, Switch, TextEditor, toast } from 'frappe-ui'
import { useOnboarding, useTelemetry } from 'frappe-ui/frappe'
import { computed, inject, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { sanitizeHTML } from '@/utils'
import MultiSelect from '@/components/Controls/MultiSelect.vue'
import Link from '@/components/Controls/Link.vue'
import NewMemberModal from '@/components/Modals/NewMemberModal.vue'

const show = defineModel<boolean>({ required: true, default: false })
const router = useRouter()
const { capture } = useTelemetry()
const { updateOnboardingStep } = useOnboarding('learning')
const user = inject<any>('$user')
const showMemberModal = ref(false)

const props = defineProps<{
	events: any
}>()

type Batch = {
	title: string
	start_date: string | null
	end_date: string | null
	start_time: string | null
	end_time: string | null
	timezone: string | null
	description: string
	event_details: string
	instructors: string[]
	categories: string[]
	seat_count: number
	medium: string | null
	event_type: string | null
	credit_hours: number | null
	venue: string
	paid_event: boolean
	amount: number | null
	currency: string | null
}

const batch = ref<Batch>({
	title: '',
	start_date: null,
	end_date: null,
	start_time: null,
	end_time: null,
	timezone: null,
	description: '',
	event_details: '',
	instructors: [],
	categories: [],
	seat_count: 0,
	medium: null,
	event_type: null,
	credit_hours: null,
	venue: '',
	paid_event: false,
	amount: null,
	currency: 'USD',
})

const onInstructorCreated = (user: any) => {
	batch.value.instructors = [...batch.value.instructors, user.name]
}

const validateFields = () => {
	Object.keys(batch.value).forEach((key) => {
		if (typeof batch.value[key as keyof Batch] === 'string') {
			batch.value[key as keyof Batch] = sanitizeHTML(
				batch.value[key as keyof Batch] as string
			)
		}
	})
}

const saveBatch = (close: () => void = () => {}) => {
	validateFields()
	props.events.insert.submit(
		{
			...batch.value,
			instructors: batch.value.instructors.map((instructor) => ({
				instructor: instructor,
			})),
			categories: batch.value.categories.map((category) => ({ category })),
		},
		{
			onSuccess(data: any) {
				toast.success(__('Event created successfully'))
				close()
				capture('event_created')
				router.push({
					name: 'EventDetail',
					params: { eventName: data.name },
					hash: '#settings',
				})
				if (user.data?.is_system_manager) {
					updateOnboardingStep('create_first_event', true, false, () => {
						localStorage.setItem('firstEvent', data.name)
					})
				}
			},
			onError(err: any) {
				toast.error(cleanError(err.messages?.[0]))
				console.error(err)
			},
		}
	)
}

const keyboardShortcut = (e: KeyboardEvent) => {
	if (
		e.key === 's' &&
		(e.ctrlKey || e.metaKey) &&
		e.target &&
		e.target instanceof HTMLElement &&
		!e.target.classList.contains('ProseMirror')
	) {
		saveBatch()
		e.preventDefault()
	}
}

onMounted(() => {
	window.addEventListener('keydown', keyboardShortcut)
	capture('event_form_opened')
})

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
	capture('event_form_closed', {
		data: batch.value,
	})
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
</script>
