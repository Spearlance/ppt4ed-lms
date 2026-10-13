<template>
	<div class="space-y-3" data-testid="license-fields">
		<FormControl
			v-model="model.license_type"
			type="select"
			:label="__('License type')"
			:options="licenseTypeOptions"
			:required="true"
		/>
		<div class="grid grid-cols-3 gap-3">
			<FormControl
				v-model="model.license_state"
				:label="__('State')"
				placeholder="FL"
				maxlength="10"
				autocomplete="off"
				class="col-span-1"
				:required="true"
				@input="model.license_state = $event.target.value.toUpperCase()"
			/>
			<FormControl
				v-model="model.professional_license_number"
				:label="__('License number')"
				autocomplete="off"
				class="col-span-2"
				:required="true"
			/>
		</div>
	</div>
</template>

<script setup>
// The three fields the CEU broker needs, shared by the register modal, the
// in-app banner and the pre-checkout dialog so every path stores the same
// shape. Validation of the triple lives in lms.lms.license on the server.
import { FormControl } from 'frappe-ui'

const model = defineModel({
	type: Object,
	default: () => ({
		license_type: '',
		license_state: '',
		professional_license_number: '',
	}),
})

const licenseTypeOptions = [
	{ label: __('Select one'), value: '' },
	{ label: __('OT — Occupational Therapy'), value: 'OT' },
	{ label: __('PT — Physical Therapy'), value: 'PT' },
	{ label: __('SLP — Speech-Language Pathology'), value: 'SLP' },
	{ label: __('Other'), value: 'Other' },
]
</script>
