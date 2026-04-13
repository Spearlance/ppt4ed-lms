<template>
    <div
        v-if="showBanner"
        class="rounded-lg p-4 flex items-center justify-between"
        :class="bannerClasses"
    >
        <div class="flex items-center gap-3">
            <AlertTriangle class="size-5 shrink-0" :class="iconClass" />
            <div>
                <div class="text-sm font-medium" :class="titleClass">
                    {{ title }}
                </div>
                <div class="text-xs mt-0.5" :class="subtitleClass">
                    {{ subtitle }}
                </div>
            </div>
        </div>
        <div class="flex items-center gap-2">
            <Button variant="subtle" size="sm" @click="handleCta">
                {{ ctaLabel }}
            </Button>
            <button
                @click="dismiss"
                class="p-1 rounded hover:bg-black/5 transition-colors"
                :aria-label="__('Dismiss')"
            >
                <X class="size-4" :class="iconClass" />
            </button>
        </div>
    </div>
</template>

<script setup lang="ts">
import { Button } from 'frappe-ui'
import { computed, ref, inject } from 'vue'
import { useRouter } from 'vue-router'
import { AlertTriangle, X } from 'lucide-vue-next'

const user = inject<any>('$user')
const router = useRouter()

const dismissed = ref(sessionStorage.getItem('low-credit-alert-dismissed') === 'true')

const PROFESSIONAL_THRESHOLD = 3

const balance = computed(() => {
    if (!user?.data) return null
    if (user.data.membership_type === 'professional') return user.data.credit_balance ?? null
    if (user.data.membership_type === 'company') return user.data.company_credit_balance ?? null
    return null
})

const threshold = computed(() => {
    if (!user?.data) return 0
    if (user.data.membership_type === 'professional') return PROFESSIONAL_THRESHOLD
    if (user.data.membership_type === 'company') {
        const t = user.data.low_credit_threshold ?? 8
        return t === 0 ? 0 : t  // 0 = disabled
    }
    return 0
})

const isLow = computed(() => {
    if (balance.value === null || threshold.value === 0) return false
    return balance.value < threshold.value && balance.value > 0
})

const isZero = computed(() => {
    if (balance.value === null) return false
    return balance.value <= 0
})

const showBanner = computed(() => {
    if (dismissed.value) return false
    if (!user?.data?.name) return false
    const type = user.data.membership_type
    if (!type || type === 'one_off' || type === 'ppt_employee') return false
    return isLow.value || isZero.value
})

const isCompanyAdmin = computed(() => user?.data?.is_company_admin)
const isCompany = computed(() => user?.data?.membership_type === 'company')

const bannerClasses = computed(() => {
    if (isZero.value) return 'bg-surface-red-2 border border-outline-red-2'
    return 'bg-surface-amber-1 border border-outline-amber-1'
})

const iconClass = computed(() => isZero.value ? 'text-ink-red-3' : 'text-ink-amber-3')
const titleClass = computed(() => isZero.value ? 'text-ink-red-3' : 'text-ink-amber-3')
const subtitleClass = computed(() => isZero.value ? 'text-ink-red-2' : 'text-ink-amber-2')

const title = computed(() => {
    if (isZero.value) return __('No credits remaining')
    const b = balance.value
    return __('Low credit balance — {0} CEU hours remaining').format(b)
})

const subtitle = computed(() => {
    if (isCompany.value && !isCompanyAdmin.value) {
        return isZero.value
            ? __('Contact your administrator to add more credits')
            : __('Contact your administrator to add more credits')
    }
    if (isZero.value) return __('Purchase credits to enroll in courses')
    return __('Top up to continue enrolling in courses')
})

const ctaLabel = computed(() => {
    if (isCompany.value && !isCompanyAdmin.value) return __('View Credits')
    return __('Add Credits')
})

const handleCta = () => {
    if (isCompany.value && !isCompanyAdmin.value) {
        router.push({ name: 'MyCredits' })
    } else {
        window.location.href = '/lms/membership-plans'
    }
}

const dismiss = () => {
    dismissed.value = true
    sessionStorage.setItem('low-credit-alert-dismissed', 'true')
}
</script>
