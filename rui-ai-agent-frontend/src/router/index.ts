import { createRouter, createWebHistory } from "vue-router";
import HomePage from "@/views/HomePage.vue";
import LoveChatPage from "@/views/LoveChatPage.vue";
import ManusChatPage from "@/views/ManusChatPage.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomePage },
    { path: "/love", name: "love", component: LoveChatPage },
    { path: "/manus", name: "manus", component: ManusChatPage },
  ],
});

