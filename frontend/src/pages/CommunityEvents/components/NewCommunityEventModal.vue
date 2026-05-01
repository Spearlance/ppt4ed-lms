<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('New Community Event'),
			size: '2xl',
		}"
	>
		<template #body-content>
			<div class="space-y-4 text-base">
				<FormControl
					v-model="form.title"
					:label="__('Title')"
					:required="true"
					autocomplete="off"
				/>
				<div class="grid grid-cols-2 gap-4">
					<FormControl
						v-model="form.start_date"
						:label="__('Start Date')"
						type="date"
						:required="true"
					/>
					<FormControl
						v-model="form.end_date"
						:label="__('End Date (optional)')"
						type="date"
					/>
				</div>
				<div class="grid grid-cols-2 gap-4">
					<FormControl
						v-model="form.start_time"
						:label="__('Start Time')"
						type="time"
					/>
					<FormControl
						v-model="form.end_time"
						:label="__('End Time')"
						type="time"
					/>
				</div>
				<FormControl
					v-model="form.location"
					:label="__('Location')"
					:placeholder="__('Address or \'Virtual\'')"
				/>
				<div class="grid grid-cols-2 gap-4">
					<FormControl
						v-model.number="form.max_attendees"
						:label="__('Max Attendees (0 = unlimited)')"
						type="number"
						min="0"
					/>
					<FormControl
						v-model.number="form.additional_attendee_amount"
						:label="__('Donation per Extra Attendee (USD)')"
						type="number"
						min="0"
						step="0.01"
					/>
				</div>
				<p class="text-xs text-ink-gray-5">
					{{ __('First attendee per signup is always free. Additional attendees are charged this amount as a donation. Set to 0 for fully free events.') }}
				</p>
			</div>
		</template>
		<template #actions="{ close }">
			<div class="text-right">
				<Button variant="solid" :loading="saving" @click="save(close)">
					{{ __('Create') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref } from 'vue'
import { Button, call, Dialog, FormControl, toast } from 'frappe-ui'

const show = defineModel({ required: true, default: false })
const emit = defineEmits(['created'])

const saving = ref(false)
const form = ref({
	title: '',
	start_date: null,
	end_date: null,
	start_time: null,
	end_time: null,
	location: '',
	max_attendees: 0,
	additional_attendee_amount: 0,
})

const save = async (close) => {
	if (!form.value.title || !form.value.start_date) {
		toast.error(__('Title and start date are required.'))
		return
	}
	saving.value = true
	try {
		const doc = await call('frappe.client.insert', {
			doc: {
				doctype: 'Community Event',
				title: form.value.title,
				start_date: form.value.start_date,
				end_date: form.value.end_date || form.value.start_date,
				start_time: form.value.start_time || null,
				end_time: form.value.end_time || null,
				location: form.value.location || null,
				max_attendees: form.value.max_attendees || 0,
				additional_attendee_amount: form.value.additional_attendee_amount || 0,
				published: 0,
			},
		})
		toast.success(__('Community event created'))
		close()
		emit('created', doc.name)
	} catch (err) {
		toast.error(err.messages?.[0] || __('Could not create event'))
	} finally {
		saving.value = false
	}
}
</script>
