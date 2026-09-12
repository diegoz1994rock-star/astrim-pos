package com.astrim.pos

import android.app.Application
import com.astrim.pos.core.AppContainer

class AstrimApplication : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
