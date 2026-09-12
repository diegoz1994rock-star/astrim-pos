package com.astrim.pos

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import com.astrim.pos.core.LocalAppContainer
import com.astrim.pos.ui.AstrimApp
import com.astrim.pos.ui.theme.AstrimTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val container = (application as AstrimApplication).container

        setContent {
            CompositionLocalProvider(LocalAppContainer provides container) {
                AstrimTheme {
                    Surface(
                        modifier = Modifier.fillMaxSize(),
                        color = MaterialTheme.colorScheme.background,
                    ) {
                        AstrimApp(sessionRepository = container.sessionRepository)
                    }
                }
            }
        }
    }
}
