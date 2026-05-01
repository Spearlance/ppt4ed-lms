<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Make an Announcement'),
			size: 'xl',
			actions: [
				{
					label: 'Send Announcement',
					variant: 'solid',
					onClick: (close) => makeAnnouncement(close),
					loading: announcementResource.loading,
				},
			],
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<FormControl
					:label="__('Subject')"
					type="text"
					v-model="announcement.subject"
					:placeholder="subjectPlaceholder"
					:required="true"
				/>
				<div>
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Announcement') }}
						<span class="text-ink-red-3">*</span>
					</div>
					<TextEditor
						:fixedMenu="true"
						@change="(val) => (announcement.body = val)"
						editorClass="prose-sm py-2 px-2 min-h-[200px] border-outline-gray-2 hover:border-outline-gray-3 rounded-b-md bg-surface-gray-3"
					/>
					<p class="mt-2 text-xs text-ink-gray-5">
						{{
							__(
								'Sent to all enrolled attendees by email and as an in-app notification. Replies go to your account email.'
							)
						}}
					</p>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, FormControl, TextEditor, createResource, toast } from 'frappe-ui'
import { computed, reactive } from 'vue'

const show = defineModel()

const props = defineProps({
	event: {
		type: String,
		required: true,
	},
	eventTitle: {
		type: String,
		default: '',
	},
})

const emit = defineEmits(['posted'])

const announcement = reactive({
	subject: '',
	body: '',
})

const subjectPlaceholder = computed(() =>
	props.eventTitle
		? __('e.g. Reminder for {0}').replace('{0}', props.eventTitle)
		: __('What is this announcement about?')
)

const announcementResource = createResource({
	url: 'lms.lms.api.post_event_announcement',
	makeParams() {
		return {
			event: props.event,
			subject: announcement.subject,
			body: announcement.body,
		}
	},
})

const makeAnnouncement = (close) => {
	announcementResource.submit(
		{},
		{
			validate() {
				if (!announcement.subject?.trim()) {
					return __('Subject is required')
				}
				if (!announcement.body?.trim()) {
					return __('Announcement is required')
				}
			},
			onSuccess() {
				toast.success(__('Announcement sent'))
				announcement.subject = ''
				announcement.body = ''
				emit('posted')
				close()
			},
			onError(err) {
				toast.error(__(err.messages?.[0] || err))
			},
		}
	)
}
</script>
