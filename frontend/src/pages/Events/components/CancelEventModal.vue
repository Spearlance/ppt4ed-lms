<template>
	<Dialog v-model="show" :options="{ title: __('Cancel this event?'), size: 'lg' }">
		<template #body-content>
			<div class="space-y-4 text-base text-ink-gray-8" data-testid="cancel-event-dialog">
				<p>
					{{
						__(
							'Cancelling takes the event off the public listings, closes registration and stops all reminders. Registered attendees can still open it and will see that it was cancelled.'
						)
					}}
				</p>
				<p class="font-medium text-ink-gray-9" data-testid="cancel-registrations">
					{{ registrationsLabel }}
				</p>
				<FormControl
					v-model="message"
					type="textarea"
					:rows="4"
					:maxlength="1000"
					:label="__('Message to attendees (optional)')"
					:description="
						__(
							'Shown on the event page for registered attendees, and included in the email if you send one.'
						)
					"
				/>
				<label class="flex items-start gap-2 cursor-pointer">
					<input
						v-model="notify"
						type="checkbox"
						class="mt-0.5 rounded border-outline-gray-3"
						data-testid="cancel-notify"
						:disabled="!registrations"
					/>
					<span>
						<span class="text-ink-gray-9">
							{{ __('Email the registered attendees') }}
						</span>
						<span class="block text-sm text-ink-gray-6">
							{{
								notify
									? __('{0} will be emailed as soon as you confirm.').format(
											registrationsLabelShort
									  )
									: __('No email will be sent.')
							}}
						</span>
					</span>
				</label>
				<p
					v-if="info.data?.paid_event"
					class="rounded-md bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3"
				>
					{{
						__(
							'This is a paid event. Cancelling does not refund anyone. Issue refunds in Stripe.'
						)
					}}
				</p>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button @click="show = false">{{ __('Keep event') }}</Button>
				<Button
					variant="solid"
					theme="red"
					:loading="cancelling"
					:label="notify ? __('Cancel event and send email') : __('Cancel event')"
					@click="confirm"
				/>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Button, Dialog, FormControl, call, createResource, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const show = defineModel()
const props = defineProps({
	event: { type: String, required: true },
})
const emit = defineEmits(['cancelled'])

const message = ref('')
const notify = ref(false)
const cancelling = ref(false)

const info = createResource({
	url: 'lms.lms.event_cancel.get_cancel_info',
	makeParams() {
		return { event: props.event }
	},
})

const registrations = computed(() => info.data?.registrations || 0)

const registrationsLabelShort = computed(() =>
	registrations.value === 1
		? __('1 person')
		: __('{0} people').format(registrations.value)
)

const registrationsLabel = computed(() => {
	if (!info.data) return ''
	if (!registrations.value) return __('Nobody is registered for this event.')
	return registrations.value === 1
		? __('1 person is registered for this event.')
		: __('{0} people are registered for this event.').format(registrations.value)
})

watch(show, (open) => {
	if (!open) return
	// Every opening starts from the safe defaults: no message, no email.
	message.value = ''
	notify.value = false
	info.reload()
})

const confirm = () => {
	cancelling.value = true
	call('lms.lms.event_cancel.cancel_event', {
		event: props.event,
		notify: notify.value ? 1 : 0,
		message: message.value,
	})
		.then((result) => {
			show.value = false
			toast.success(
				result.notified
					? __('Event cancelled. {0} emailed.').format(
							result.notified === 1
								? __('1 attendee')
								: __('{0} attendees').format(result.notified)
					  )
					: __('Event cancelled. No email was sent.')
			)
			emit('cancelled')
		})
		.catch((error) => {
			toast.error(
				error?.messages?.[0] ||
					__('This event could not be cancelled. Nothing was changed.')
			)
		})
		.finally(() => {
			cancelling.value = false
		})
}
</script>
