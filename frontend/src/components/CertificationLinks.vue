<template>
	<Button
		v-if="certification.data && certification.data.certificate"
		@click="downloadCertificate"
	>
		<template #prefix>
			<GraduationCap class="size-4 stroke-1.5" />
		</template>
		{{ __('View Certificate') }}
	</Button>
</template>
<script setup>
import { Button, createResource } from 'frappe-ui'
import { inject } from 'vue'
import { GraduationCap } from 'lucide-vue-next'

const user = inject('$user')

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
})

const certification = createResource({
	url: 'lms.lms.api.get_certification_details',
	makeParams(values) {
		return {
			course: props.courseName,
		}
	},
	auto: user.data ? true : false,
})

const downloadCertificate = () => {
	window.open(
		`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate&name=${
			certification.data.certificate.name
		}&format=${encodeURIComponent(certification.data.certificate.template)}&pdf_generator=chrome`
	)
}
</script>
