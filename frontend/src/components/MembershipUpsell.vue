<template>
    <div
        v-if="showBanner"
        class="bg-surface-blue-2 border border-outline-blue-2 rounded-lg p-4 flex items-center justify-between"
    >
        <div class="flex items-center gap-3">
            <Sparkles class="size-5 text-ink-blue-3 shrink-0" />
            <div>
                <div class="text-sm font-medium text-ink-blue-3">
                    {{ __('Unlock all courses with a Professional membership') }}
                </div>
                <div class="text-xs text-ink-blue-2 mt-0.5">
                    {{ __('Get a credit bank and access the full course catalog') }}
                </div>
            </div>
        </div>
        <Button variant="subtle" size="sm" @click="navigateToPlans">
            {{ __('View Plans') }}
        </Button>
    </div>
</template>

<script setup lang="ts">
import { Button, createResource } from 'frappe-ui'
import { computed, inject } from 'vue'
import { Sparkles } from 'lucide-vue-next'

const user = inject('$user')

const userType = createResource({
    url: 'lms.lms.lms.ceu_user_type.get_user_type',
    auto: !!user?.data?.name,
})

const showBanner = computed(() => {
    return user?.data?.name && userType.data?.type === 'one_off'
})

const navigateToPlans = () => {
    window.location.href = '/lms/membership-plans'
}
</script>
