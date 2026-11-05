<template>
	<div>
		<header
			class="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-2 border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<div class="flex flex-wrap items-center gap-2">
				<template v-if="!isSampleMode">
					<input
						v-model="certNameInput"
						:placeholder="__('LMS Certificate name')"
						class="rounded border px-2 py-1 text-sm"
						@keydown.enter="loadCertificate"
					/>
					<Button :label="__('Load')" @click="loadCertificate" />
				</template>
				<Button
					v-else
					:label="__('Refresh')"
					:loading="samplePreview.loading"
					@click="samplePreview.reload()"
				/>
				<Button
					variant="solid"
					:label="__('Download PDF')"
					:disabled="!canDownload"
					@click="downloadPdf"
				/>
			</div>
		</header>

		<div class="p-5">
			<div
				v-if="isSampleMode"
				class="mb-4 rounded-lg border border-outline-gray-2 bg-surface-amber-1 p-3 text-sm text-ink-gray-8"
				data-testid="sample-preview-banner"
			>
				<span class="font-semibold">{{ __('Sample certificate.') }}</span>
				{{
					__(
						'Rendered with the same template, signers, credentials, hours, date and format an attendee would receive. Nothing is issued, recorded or emailed by opening this page.'
					)
				}}
				<span v-if="samplePreview.data?.event_title">
					{{ __('Event: {0}').format(samplePreview.data.event_title) }}
				</span>
				<span v-else-if="samplePreview.data?.course_title">
					{{ __('Course: {0}').format(samplePreview.data.course_title) }}
				</span>
			</div>

			<div v-if="samplePreview.error" class="text-ink-red-4 text-sm" data-testid="sample-preview-error">
				{{ samplePreview.error?.messages?.[0] || __('Could not render the sample certificate.') }}
			</div>

			<div v-else-if="!isSampleMode && !certName" class="text-ink-gray-6">
				{{ __('Enter an LMS Certificate document name to preview it.') }}
			</div>

			<div v-else class="cert-stage">
				<iframe
					v-if="isSampleMode"
					ref="printIframe"
					:srcdoc="samplePreview.data?.html || ''"
					class="cert-iframe"
					:title="__('Sample certificate preview')"
					data-testid="sample-preview-frame"
				></iframe>
				<iframe
					v-else
					ref="printIframe"
					:src="printViewUrl"
					class="cert-iframe"
					:title="__('Certificate preview')"
				></iframe>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Breadcrumbs, Button, createResource, usePageMeta } from 'frappe-ui'

const props = defineProps({
	certName: { type: String, default: '' },
	eventName: { type: String, default: '' },
	courseName: { type: String, default: '' },
})

const router = useRouter()
const certNameInput = ref(props.certName || '')
const printIframe = ref(null)

usePageMeta({ title: 'Certificate Preview' })

// Sample mode renders a course's or event's certificate for a placeholder
// participant; the real-certificate mode below loads an issued LMS Certificate.
const isSampleMode = computed(() => Boolean(props.eventName || props.courseName))

const sampleParams = () => {
	if (props.eventName) return { event: props.eventName }
	return { course: props.courseName }
}

const samplePreview = createResource({
	url: 'lms.lms.ceu_event_admin.preview_sample_certificate',
	makeParams() {
		return sampleParams()
	},
})

const breadcrumbs = computed(() => {
	if (props.eventName) {
		return [
			{ label: __('Events'), route: { name: 'Events' } },
			{
				label: samplePreview.data?.event_title || props.eventName,
				route: { name: 'EventDetail', params: { eventName: props.eventName } },
			},
			{ label: __('Sample certificate') },
		]
	}
	if (props.courseName) {
		return [
			{ label: __('Courses'), route: { name: 'Courses' } },
			{
				label: samplePreview.data?.course_title || props.courseName,
				route: { name: 'CourseDetail', params: { courseName: props.courseName } },
			},
			{ label: __('Sample certificate') },
		]
	}
	return [
		{
			label: __('Certificate Preview'),
			route: { name: 'CertificatePreview', params: { certName: props.certName } },
		},
	]
})

const canDownload = computed(() =>
	isSampleMode.value ? Boolean(samplePreview.data?.html) : Boolean(props.certName)
)

const printViewUrl = computed(() => {
	if (!props.certName) return ''
	const params = new URLSearchParams({
		doctype: 'LMS Certificate',
		name: props.certName,
		format: 'Certificate',
		no_letterhead: '1',
	})
	return `/printview?${params.toString()}`
})

const loadCertificate = () => {
	const target = certNameInput.value.trim()
	if (!target || target === props.certName) return
	router.push({ name: 'CertificatePreview', params: { certName: target } })
}

const downloadPdf = () => {
	if (isSampleMode.value) {
		const params = new URLSearchParams(sampleParams())
		window.open(
			`/api/method/lms.lms.ceu_event_admin.preview_sample_certificate_pdf?${params.toString()}`,
			'_blank'
		)
		return
	}
	if (!props.certName) return
	const params = new URLSearchParams({
		doctype: 'LMS Certificate',
		name: props.certName,
		format: 'Certificate',
		no_letterhead: '1',
		pdf_generator: 'chrome',
	})
	window.open(`/api/method/frappe.utils.print_format.download_pdf?${params.toString()}`, '_blank')
}

watch(
	() => props.certName,
	(next) => {
		certNameInput.value = next || ''
	}
)

watch(
	() => [props.eventName, props.courseName],
	([event, course]) => {
		if (event || course) samplePreview.reload()
	},
	{ immediate: true }
)
</script>

<style scoped>
.cert-stage {
	display: flex;
	justify-content: center;
	background: #f3f4f6;
	padding: 1rem;
	border-radius: 0.5rem;
}

.cert-iframe {
	width: 11in;
	height: 8.5in;
	max-width: 100%;
	background: white;
	border: 1px solid #d1d5db;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
	/* Scale the 11in iframe to fit narrow viewports. */
	transform-origin: top center;
}

@media (max-width: 1200px) {
	.cert-iframe {
		transform: scale(0.75);
		margin-bottom: -2.125in;
	}
}

@media (max-width: 900px) {
	.cert-iframe {
		transform: scale(0.55);
		margin-bottom: -3.825in;
	}
}
</style>
