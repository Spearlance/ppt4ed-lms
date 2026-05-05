<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Survey QR Code'),
			size: 'md',
		}"
	>
		<template #body-content>
			<div v-if="qrResource.loading" class="text-center py-12 text-ink-gray-7">
				{{ __('Generating QR code…') }}
			</div>
			<div
				v-else-if="qrResource.error"
				class="text-center py-12 text-ink-red-3"
			>
				{{ __('Failed to generate QR code. Please try again.') }}
			</div>
			<div v-else-if="qrResource.data" class="flex flex-col items-center gap-4">
				<img
					:src="qrResource.data.data_uri"
					:alt="__('Survey QR code')"
					class="w-64 h-64 border border-outline-gray-2 rounded-md p-3 bg-white"
				/>
				<div class="text-sm text-ink-gray-7 text-center max-w-md">
					{{
						__(
							'Scanning this code opens the event page where attendees can take the feedback survey.'
						)
					}}
				</div>
				<a
					:href="qrResource.data.data_uri"
					:download="downloadFilename"
				>
					<Button variant="solid">
						<template #prefix>
							<Download class="size-4 stroke-1.5" />
						</template>
						{{ __('Download PNG') }}
					</Button>
				</a>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { computed, watch } from 'vue'
import { Button, Dialog, createResource } from 'frappe-ui'
import { Download } from 'lucide-vue-next'

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

const qrResource = createResource({
	url: 'lms.lms.api.get_event_survey_qr',
	makeParams() {
		return { event: props.event }
	},
})

watch(show, (open) => {
	if (open && !qrResource.data) {
		qrResource.submit()
	}
})

const downloadFilename = computed(() => {
	const slug = (props.eventTitle || props.event || 'event')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
	return `${slug}-survey-qr.png`
})
</script>
