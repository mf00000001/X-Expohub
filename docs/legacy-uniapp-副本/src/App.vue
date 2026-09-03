<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup lang="ts">
// Root component — layout is delegated to child views
</script>

<style>
#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
</style>
