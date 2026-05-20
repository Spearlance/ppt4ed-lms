<template>
	<div>
		<header
			class="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-2 border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs
				class="h-7"
				:items="[
					{ label: __('Certificate Preview'), route: { name: 'CertificatePreview', params: { certName } } },
				]"
			/>
			<div class="flex items-center gap-2">
				<input
					v-model="certNameInput"
					:placeholder="__('LMS Certificate name')"
					class="rounded border px-2 py-1 text-sm"
					@keydown.enter="loadCertificate"
				/>
				<Button :label="__('Load')" @click="loadCertificate" />
				<Button
					variant="solid"
					:label="__('Download PDF')"
					:disabled="!certName"
					@click="downloadPdf"
				/>
			</div>
		</header>

		<div class="p-5">
			<div v-if="!certName" class="text-ink-gray-6">
				{{ __('Enter an LMS Certificate document name to preview it.') }}
			</div>

			<div v-else class="cert-stage">
				<iframe
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
import { Breadcrumbs, Button, usePageMeta } from 'frappe-ui'

const props = defineProps({
	certName: { type: String, default: '' },
})

const router = useRouter()
const certNameInput = ref(props.certName || '')
const printIframe = ref(null)

usePageMeta({ title: 'Certificate Preview' })

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
	},
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
